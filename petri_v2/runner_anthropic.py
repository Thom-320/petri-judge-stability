"""Anthropic Message Batches runner.

API shapes checked 2026-10-09:
  https://platform.claude.com/docs/en/api/messages/batches/create
  https://platform.claude.com/docs/en/build-with-claude/batch-processing
  - POST /v1/messages/batches  body {"requests": [{"custom_id", "params"}]}; custom_id ^[a-zA-Z0-9_-]{1,64}$
  - GET  /v1/messages/batches/{id}  processing_status: in_progress | canceling | ended; results_url once ended
  - GET  results_url -> JSONL {"custom_id", "result": {"type": succeeded|errored|canceled|expired, "message"|"error"}}
  - limits: 100,000 requests or 256 MB per batch; batches expire 24 h after creation; results kept 29 days
  - headers: x-api-key, anthropic-version: 2023-06-01 (no beta header needed for batches)
  - 50% batch discount; extended thinking is supported in batches.

Usage:
  python -m petri_v2.runner_anthropic plan
  python -m petri_v2.runner_anthropic run --budget-usd 80 --confirm-spend      # needs ANTHROPIC_API_KEY
"""
import json
import sys

from . import batch, http

API = "https://api.anthropic.com/v1"
VERSION = "2023-06-01"


class AnthropicRunner(batch.BatchRunner):
    provider = "anthropic"
    key_env = "ANTHROPIC_API_KEY"
    max_requests = 100_000
    max_bytes = 256 * 1024 * 1024 - 1024 * 1024  # 1 MB headroom for the JSON envelope

    def headers(self):
        return {"x-api-key": self.key(), "anthropic-version": VERSION, "content-type": "application/json"}

    def submit_batch(self, lines, label):
        body = json.dumps({"requests": lines}, ensure_ascii=False).encode("utf-8")
        r = http.check(self.transport.request("POST", f"{API}/messages/batches", self.headers(), body))
        return r.json()["id"]

    def get_status(self, batch_id):
        r = http.check(self.transport.request("GET", f"{API}/messages/batches/{batch_id}", self.headers()))
        d = r.json()
        st = d.get("processing_status")
        state = {"in_progress": "running", "canceling": "running", "ended": "ended"}.get(st, "running")
        return state, {"processing_status": st, "results_url": d.get("results_url"),
                       "request_counts": d.get("request_counts"), "expires_at": d.get("expires_at")}

    def fetch_results(self, batch_id, meta):
        url = meta.get("results_url") or f"{API}/messages/batches/{batch_id}/results"
        r = http.check(self.transport.request("GET", url, self.headers()))
        for line in r.text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            res = d.get("result") or {}
            t = res.get("type")
            if t == "succeeded":
                yield d["custom_id"], "responded", res.get("message"), None
            else:
                status = {"errored": "errored", "canceled": "canceled", "expired": "expired"}.get(t, "errored")
                yield d["custom_id"], status, None, res.get("error") or t

    def normalize(self, message):
        text = "".join(b.get("text", "") for b in message.get("content") or [] if b.get("type") == "text")
        stop = message.get("stop_reason")
        finish = {"max_tokens": "length", "refusal": "content_filter"}.get(stop, stop)
        return text, finish, message.get("usage")


def main(argv=None):
    batch.cli(AnthropicRunner, ["opus45"], argv)


if __name__ == "__main__":
    sys.exit(main())
