"""Gemini API (ai.google.dev) Batch Mode runner, file input.

API shapes checked 2026-10-09:
  https://ai.google.dev/gemini-api/docs/batch-api   (page "Last updated 2026-09-17")
  https://ai.google.dev/api/batch-mode
  - input: JSONL file, one {"key", "request"} per line, uploaded with the resumable File API
    (POST https://generativelanguage.googleapis.com/upload/v1beta/files); max input file 2 GB
  - POST /v1beta/models/{model}:batchGenerateContent  body {"batch": {"display_name", "input_config": {"file_name"}}}
  - GET  /v1beta/{batches/...}: state in metadata.state; the guide says JOB_STATE_*, the API reference
    BATCH_STATE_*; both prefixes are accepted here. Jobs expire after 48 h (no results).
  - results: response.responsesFile -> GET /download/v1beta/{file}:download?alt=media, JSONL in input order
  - auth header x-goog-api-key; 50% of standard cost; results kept 6 weeks.
gemini-3-pro-preview (Petri 2.0's judge) is shut down (2026-03-09); the default facet is the named
replacement gemini-3.1-pro-preview, labelled as a separate judge (see petri_v2/judges.py).

Usage:
  python -m petri_v2.runner_gemini plan
  python -m petri_v2.runner_gemini run --budget-usd 40 --confirm-spend         # needs GEMINI_API_KEY
"""
import json
import sys

from . import batch, http, judges

BASE = "https://generativelanguage.googleapis.com"


def _state(raw):
    s = (raw or "").replace("JOB_STATE_", "").replace("BATCH_STATE_", "")
    return {"PENDING": "running", "RUNNING": "running", "SUCCEEDED": "ended", "FAILED": "failed",
            "CANCELLED": "cancelled", "EXPIRED": "expired_no_results"}.get(s, "running")


class GeminiRunner(batch.BatchRunner):
    provider = "gemini"
    key_env = "GEMINI_API_KEY"
    max_requests = 1_000_000
    max_bytes = 2 * 1024 ** 3 - 16 * 1024 ** 2

    def upload(self, data, display_name):
        key = self.key()
        start = self.transport.request(
            "POST", f"{BASE}/upload/v1beta/files",
            {"x-goog-api-key": key, "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
             "X-Goog-Upload-Header-Content-Length": str(len(data)),
             "X-Goog-Upload-Header-Content-Type": "application/jsonl", "Content-Type": "application/json"},
            json.dumps({"file": {"display_name": display_name}}).encode())
        http.check(start)
        upload_url = start.headers.get("x-goog-upload-url")
        if not upload_url:
            raise RuntimeError("Gemini upload: no x-goog-upload-url header in the start response")
        r = http.check(self.transport.request(
            "POST", upload_url,
            {"x-goog-api-key": key, "Content-Length": str(len(data)), "X-Goog-Upload-Offset": "0",
             "X-Goog-Upload-Command": "upload, finalize"}, data))
        return r.json()["file"]["name"]

    def submit_batch(self, lines, label):
        model = judges.get(label).model
        data = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines).encode("utf-8")
        name = f"petri-v2-{label}-{len(lines)}"
        file_name = self.upload(data, name)
        body = {"batch": {"display_name": name, "input_config": {"file_name": file_name}}}
        r = http.check(self.transport.request(
            "POST", f"{BASE}/v1beta/models/{model}:batchGenerateContent",
            {"x-goog-api-key": self.key(), "Content-Type": "application/json"}, json.dumps(body).encode()))
        return r.json()["name"]

    def get_status(self, batch_id):
        r = http.check(self.transport.request("GET", f"{BASE}/v1beta/{batch_id}", {"x-goog-api-key": self.key()}))
        d = r.json()
        md = d.get("metadata") or {}
        raw = md.get("state") or d.get("state")
        resp = d.get("response") or {}
        out = resp.get("responsesFile") or (md.get("output") or {}).get("responsesFile") \
            or (d.get("dest") or {}).get("fileName")
        return _state(raw), {"state": raw, "responses_file": out, "done": d.get("done")}

    def fetch_results(self, batch_id, meta):
        f = meta.get("responses_file")
        if not f:
            raise RuntimeError(f"batch {batch_id} ended without a responses file")
        r = http.check(self.transport.request(
            "GET", f"{BASE}/download/v1beta/{f}:download?alt=media", {"x-goog-api-key": self.key()}))
        for line in r.text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("response") is not None:
                yield d["key"], "responded", d["response"], None
            else:
                yield d["key"], "errored", None, d.get("error") or d.get("status") or "no response"

    def normalize(self, resp):
        cands = resp.get("candidates") or []
        c = cands[0] if cands else {}
        parts = (c.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        finish = c.get("finishReason")
        if not cands and (resp.get("promptFeedback") or {}).get("blockReason"):
            finish = "content_filter"
        finish = {"MAX_TOKENS": "length", "SAFETY": "content_filter", "STOP": "stop"}.get(finish, finish)
        u = resp.get("usageMetadata") or {}
        usage = {"input_tokens": u.get("promptTokenCount"),
                 "output_tokens": (u.get("candidatesTokenCount") or 0) + (u.get("thoughtsTokenCount") or 0),
                 "thoughts_tokens": u.get("thoughtsTokenCount"), "raw": u}
        return text, finish, usage


def main(argv=None):
    batch.cli(GeminiRunner, ["gemini31pro"], argv)


if __name__ == "__main__":
    sys.exit(main())
