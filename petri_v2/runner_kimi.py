"""Moonshot (Kimi) Batch API runner for the open-weight judge `kimik26` (kimi-k2.6).

API shapes checked 2026-10-10 (https://platform.kimi.ai/docs/guide/use-batch-api,
https://platform.kimi.ai/docs/pricing/batch):
  - base URL https://api.moonshot.ai/v1 (OpenAI-compatible); Authorization: Bearer <MOONSHOT_API_KEY>
  - POST /v1/files (multipart, purpose=batch); JSONL lines
    {"custom_id", "method": "POST", "url": "/v1/chat/completions", "body"}; file .jsonl, non-empty,
    <= 100 MB; one model per file; custom_id unique
  - POST /v1/batches {"input_file_id", "endpoint": "/v1/chat/completions", "completion_window": "24h"}
  - GET  /v1/batches/{id}: status validating | failed | in_progress | finalizing | completed | expired |
    cancelling | cancelled; output_file_id, error_file_id, request_counts
  - GET  /v1/files/{id}/content -> JSONL {"custom_id", "response": {"status_code", "body"}, "error"}
  - Batch models: kimi-k2.7-code and kimi-k2.6 only. "The temperature, top_p, n, presence_penalty,
    and frequency_penalty parameters cannot be modified for these models. Do not include these
    parameters in the body." Thinking is on by default for kimi-k2.6 (sent explicitly).
  - Price: "Batch API inference costs are 60% of the standard model price" ($0.57 / $2.40 per MTok).
  - Not stated on the pages read: a per-file request limit (50,000 assumed, as OpenAI's) and the
    error code of expired items (`batch_expired` or `expired` are both treated as expired).

Usage:
  python -m petri_v2.runner_kimi plan --start 120 --n 260
  python -m petri_v2.runner_kimi run  --start 120 --n 260 --budget-usd 10 --confirm-spend   # needs MOONSHOT_API_KEY
"""
import json
import sys

from . import batch, http

API = "https://api.moonshot.ai/v1"


def normalize_chat(body):
    """(text, finish_reason, usage) from a Chat Completions body. The reasoning trace
    (`message.reasoning_content`) is not judge output and is dropped, as Petri keeps only the answer."""
    choices = body.get("choices") or []
    if not choices:
        return "", body.get("finish_reason"), body.get("usage")
    c = choices[0]
    msg = c.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):  # tolerate content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in ("text", "output_text"))
    return content or "", c.get("finish_reason"), body.get("usage")


class KimiRunner(batch.BatchRunner):
    provider = "moonshot"
    key_env = "MOONSHOT_API_KEY"
    max_requests = 50_000                          # not documented; OpenAI's limit assumed
    max_bytes = 100 * 1024 * 1024 - 1024 * 1024    # 100 MB per file, 1 MB headroom

    def auth(self):
        return {"Authorization": f"Bearer {self.key()}"}

    def submit_batch(self, lines, label):
        data = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines).encode("utf-8")
        body, ctype = http.multipart({"purpose": "batch"}, {"file": (f"petri-v2-{label}.jsonl", data, "application/jsonl")})
        f = http.check(self.transport.request("POST", f"{API}/files", {**self.auth(), "Content-Type": ctype}, body))
        req = {"input_file_id": f.json()["id"], "endpoint": "/v1/chat/completions", "completion_window": "24h"}
        r = http.check(self.transport.request("POST", f"{API}/batches",
                                              {**self.auth(), "Content-Type": "application/json"},
                                              json.dumps(req).encode()))
        return r.json()["id"]

    def get_status(self, batch_id):
        d = http.check(self.transport.request("GET", f"{API}/batches/{batch_id}", self.auth())).json()
        st = d.get("status")
        state = {"validating": "running", "in_progress": "running", "finalizing": "running", "cancelling": "running",
                 "completed": "ended", "expired": "ended", "cancelled": "ended", "failed": "failed"}.get(st, "running")
        if st in ("cancelled", "expired") and not d.get("output_file_id") and not d.get("error_file_id"):
            state = "cancelled" if st == "cancelled" else "expired_no_results"
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
                code = err.get("code") if isinstance(err, dict) else None
                yield d["custom_id"], "expired" if code in ("batch_expired", "expired") else "errored", None, err

    def normalize(self, body):
        return normalize_chat(body)


def main(argv=None):
    batch.cli(KimiRunner, ["kimik26"], argv)


if __name__ == "__main__":
    sys.exit(main())
