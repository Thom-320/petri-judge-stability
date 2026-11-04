"""OpenAI Batch API runner (endpoint /v1/responses).

API shapes checked 2026-10-09:
  https://developers.openai.com/api/docs/guides/batch
  - POST /v1/files (multipart, purpose=batch); JSONL lines {"custom_id", "method": "POST", "url": "/v1/responses", "body"}
  - POST /v1/batches {"input_file_id", "endpoint": "/v1/responses", "completion_window": "24h"} (24h is the only window)
  - GET  /v1/batches/{id}: status validating | failed | in_progress | finalizing | completed | expired |
    cancelling | cancelled; output_file_id, error_file_id
  - GET  /v1/files/{id}/content -> JSONL {"custom_id", "response": {"status_code", "body"}, "error"}
  - limits: 50,000 requests and 200 MB per input file; output files deleted 30 days after completion;
    expired requests appear in the error file with code batch_expired. 50% batch discount.
gpt-5.1 is deprecated (removal 2027-04-01, named replacement gpt-6-sol; optional facet `gpt6sol`).

Usage:
  python -m petri_v2.runner_openai plan
  python -m petri_v2.runner_openai run --budget-usd 30 --confirm-spend         # needs OPENAI_API_KEY
"""
import json
import sys

from . import batch, http

API = "https://api.openai.com/v1"


class OpenAIRunner(batch.BatchRunner):
    provider = "openai"
    key_env = "OPENAI_API_KEY"
    max_requests = 50_000
    max_bytes = 200 * 1024 * 1024 - 1024 * 1024

    def auth(self):
        return {"Authorization": f"Bearer {self.key()}"}

    def submit_batch(self, lines, label):
        data = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines).encode("utf-8")
        body, ctype = http.multipart({"purpose": "batch"}, {"file": (f"petri-v2-{label}.jsonl", data, "application/jsonl")})
        f = http.check(self.transport.request("POST", f"{API}/files", {**self.auth(), "Content-Type": ctype}, body))
        req = {"input_file_id": f.json()["id"], "endpoint": "/v1/responses", "completion_window": "24h",
               "metadata": {"project": "petri-judge-stability-v2", "judge": label}}
        r = http.check(self.transport.request("POST", f"{API}/batches",
                                              {**self.auth(), "Content-Type": "application/json"},
                                              json.dumps(req).encode()))
        return r.json()["id"]

    def get_status(self, batch_id):
        d = http.check(self.transport.request("GET", f"{API}/batches/{batch_id}", self.auth())).json()
        st = d.get("status")
        state = {"validating": "running", "in_progress": "running", "finalizing": "running", "cancelling": "running",
                 "completed": "ended", "expired": "ended", "cancelled": "ended", "failed": "failed"}.get(st, "running")
        if st == "cancelled" and not d.get("output_file_id") and not d.get("error_file_id"):
            state = "cancelled"
        return state, {"status": st, "output_file_id": d.get("output_file_id"),
                       "error_file_id": d.get("error_file_id"), "request_counts": d.get("request_counts")}

    def _lines(self, file_id):
        if not file_id:
            return []
        r = http.check(self.transport.request("GET", f"{API}/files/{file_id}/content", self.auth()))
        return [json.loads(x) for x in r.text().splitlines() if x.strip()]

    def fetch_results(self, batch_id, meta):
        for d in self._lines(meta.get("output_file_id")) + self._lines(meta.get("error_file_id")):
            resp = d.get("response") or {}
            if resp.get("status_code") == 200 and resp.get("body") is not None:
                yield d["custom_id"], "responded", resp["body"], None
            else:
                err = d.get("error") or (resp.get("body") or {}).get("error") or {"status_code": resp.get("status_code")}
                code = (err or {}).get("code") if isinstance(err, dict) else None
                yield d["custom_id"], "expired" if code == "batch_expired" else "errored", None, err

    def normalize(self, body):
        texts = []
        for item in body.get("output") or []:
            if item.get("type") == "message":
                for part in item.get("content") or []:
                    if part.get("type") in ("output_text", "text"):
                        texts.append(part.get("text") or "")
                    elif part.get("type") == "refusal":
                        texts.append(part.get("refusal") or "")
        status = body.get("status")
        reason = (body.get("incomplete_details") or {}).get("reason")
        if status == "incomplete" and reason == "max_output_tokens":
            finish = "length"
        elif status == "incomplete" and reason == "content_filter":
            finish = "content_filter"
        else:
            finish = status
        return "".join(texts), finish, body.get("usage")


def main(argv=None):
    batch.cli(OpenAIRunner, ["gpt51"], argv)


if __name__ == "__main__":
    sys.exit(main())
