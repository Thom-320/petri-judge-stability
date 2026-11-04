"""Fake provider servers behind a fake transport (no network). Each records every request."""
import json
import re

from petri_v2.http import Response
from petri_v2.prompts import STUDY_DIMS

GOOD = ("<highlights>1. <cite id=\"1\" description=\"d\">x</cite></highlights><summary>s</summary><scores>\n"
        + "\n".join(f"{i + 1}. {d}: {i + 2}/10" for i, d in enumerate(STUDY_DIMS)) + "\n</scores><justification>j</justification>")


def ok(obj, headers=None, status=200):
    body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
    return Response(status, headers or {}, body)


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.routes = []  # (method, regex, handler)

    def route(self, method, pattern, handler):
        self.routes.append((method, re.compile(pattern), handler))

    def request(self, method, url, headers=None, body=None):
        self.calls.append({"method": method, "url": url, "headers": dict(headers or {}), "body": body})
        for m, rx, h in self.routes:
            if m == method and rx.search(url):
                return h(url, headers or {}, body)
        return Response(404, {}, b'{"error": "no route"}')


def behaviour(cid):
    """Deterministic per-request outcome: most succeed, some fail in provider-specific ways."""
    if cid.endswith("-r2") and "t000" in cid:
        return "error"
    if "t001" in cid and cid.endswith("-r1"):
        return "refusal"
    return "good"


class AnthropicServer:
    def __init__(self, t, n_polls_running=1):
        self.batches, self.polls = {}, {}
        self.n_running = n_polls_running
        t.route("POST", r"/v1/messages/count_tokens$", lambda u, h, b: ok({"input_tokens": 1234}))
        t.route("POST", r"/v1/messages/batches$", self.create)
        t.route("GET", r"/v1/messages/batches/[^/]+/results$", self.results)
        t.route("GET", r"/v1/messages/batches/[^/]+$", self.get)

    def create(self, url, h, body):
        d = json.loads(body)
        bid = f"msgbatch_{len(self.batches) + 1:03d}"
        self.batches[bid] = d["requests"]
        self.polls[bid] = 0
        return ok({"id": bid, "type": "message_batch", "processing_status": "in_progress"})

    def get(self, url, h, body):
        bid = url.rsplit("/", 1)[1]
        self.polls[bid] += 1
        st = "ended" if self.polls[bid] > self.n_running else "in_progress"
        return ok({"id": bid, "processing_status": st,
                   "results_url": f"https://api.anthropic.com/v1/messages/batches/{bid}/results" if st == "ended" else None})

    def results(self, url, h, body):
        bid = url.split("/")[-2]
        lines = []
        for r in self.batches[bid]:
            b = behaviour(r["custom_id"])
            if b == "error":
                res = {"type": "errored", "error": {"type": "invalid_request_error", "message": "bad"}}
            else:
                text = GOOD if b == "good" else "I'm sorry, I can't help with that."
                res = {"type": "succeeded", "message": {
                    "content": [{"type": "thinking", "thinking": "SECRET THOUGHTS"}, {"type": "text", "text": text}],
                    "stop_reason": "end_turn", "usage": {"input_tokens": 7000, "output_tokens": 4000}}}
            lines.append(json.dumps({"custom_id": r["custom_id"], "result": res}))
        return ok("\n".join(lines).encode())


class GeminiServer:
    UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files?upload_id=abc"

    def __init__(self, t):
        self.files, self.batches, self.polls = {}, {}, {}
        t.route("POST", r"/upload/v1beta/files\?upload_id=", self.upload_finalize)
        t.route("POST", r"/upload/v1beta/files$", self.upload_start)
        t.route("POST", r"/v1beta/models/[^:]+:batchGenerateContent$", self.create)
        t.route("GET", r"/download/v1beta/files/.+:download\?alt=media$", self.download)
        t.route("GET", r"/v1beta/batches/", self.get)

    def upload_start(self, url, h, body):
        assert h["X-Goog-Upload-Command"] == "start"
        return ok({}, headers={"X-Goog-Upload-URL": self.UPLOAD_URL})

    def upload_finalize(self, url, h, body):
        assert h["X-Goog-Upload-Command"] == "upload, finalize"
        name = f"files/in{len(self.files) + 1}"
        self.files[name] = [json.loads(x) for x in body.decode().splitlines()]
        return ok({"file": {"name": name}})

    def create(self, url, h, body):
        d = json.loads(body)
        name = f"batches/b{len(self.batches) + 1}"
        self.batches[name] = self.files[d["batch"]["input_config"]["file_name"]]
        self.polls[name] = 0
        return ok({"name": name, "metadata": {"state": "BATCH_STATE_PENDING"}})

    def get(self, url, h, body):
        name = "batches/" + url.rsplit("/", 1)[1]
        self.polls[name] += 1
        if self.polls[name] == 1:
            return ok({"name": name, "metadata": {"state": "JOB_STATE_RUNNING"}})
        return ok({"name": name, "done": True, "metadata": {"state": "JOB_STATE_SUCCEEDED"},
                   "response": {"responsesFile": f"files/out-{name.split('/')[1]}"}})

    def download(self, url, h, body):
        name = "batches/" + url.split("files/out-")[1].split(":")[0]
        lines = []
        for r in self.batches[name]:
            b = behaviour(r["key"])
            if b == "error":
                lines.append(json.dumps({"key": r["key"], "error": {"code": 400, "message": "bad"}}))
                continue
            text = GOOD if b == "good" else "I'm sorry, I can't help with that."
            lines.append(json.dumps({"key": r["key"], "response": {
                "candidates": [{"content": {"parts": [{"text": "SECRET THOUGHTS", "thought": True}, {"text": text}]},
                                "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 7000, "candidatesTokenCount": 1000, "thoughtsTokenCount": 3000}}}))
        return ok("\n".join(lines).encode())


class OpenAIServer:
    def __init__(self, t):
        self.files, self.batches, self.polls = {}, {}, {}
        t.route("POST", r"/v1/files$", self.upload)
        t.route("POST", r"/v1/batches$", self.create)
        t.route("GET", r"/v1/batches/", self.get)
        t.route("GET", r"/v1/files/[^/]+/content$", self.content)

    def upload(self, url, h, body):
        assert h["Content-Type"].startswith("multipart/form-data; boundary=")
        assert b'name="purpose"\r\n\r\nbatch' in body
        payload = body.split(b"Content-Type: application/jsonl\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
        fid = f"file-in{len(self.files) + 1}"
        self.files[fid] = [json.loads(x) for x in payload.decode().splitlines()]
        return ok({"id": fid, "purpose": "batch"})

    def create(self, url, h, body):
        d = json.loads(body)
        assert d["endpoint"] == "/v1/responses" and d["completion_window"] == "24h"
        bid = f"batch_{len(self.batches) + 1}"
        self.batches[bid] = self.files[d["input_file_id"]]
        self.polls[bid] = 0
        return ok({"id": bid, "status": "validating"})

    def get(self, url, h, body):
        bid = url.rsplit("/", 1)[1]
        self.polls[bid] += 1
        if self.polls[bid] == 1:
            return ok({"id": bid, "status": "in_progress"})
        return ok({"id": bid, "status": "completed", "output_file_id": f"file-out-{bid}", "error_file_id": f"file-err-{bid}"})

    def content(self, url, h, body):
        fid = url.split("/")[-2]
        bid = fid.split("-", 2)[2]
        out = []
        for r in self.batches[bid]:
            b = behaviour(r["custom_id"])
            if fid.startswith("file-err") and b == "error":
                out.append({"custom_id": r["custom_id"], "response": None,
                            "error": {"code": "batch_expired", "message": "expired"}})
            elif fid.startswith("file-out") and b != "error":
                text = GOOD if b == "good" else "I'm sorry, I can't help with that."
                out.append({"custom_id": r["custom_id"], "response": {"status_code": 200, "body": {
                    "status": "completed", "output": [{"type": "reasoning", "summary": []},
                                                      {"type": "message", "content": [{"type": "output_text", "text": text}]}],
                    "usage": {"input_tokens": 7000, "output_tokens": 4000}}}, "error": None})
        return ok("\n".join(json.dumps(x) for x in out).encode())


def chat_completion(text):
    return {"id": "chatcmpl-x", "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text,
                                                 "reasoning_content": "SECRET THOUGHTS"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 7000, "completion_tokens": 4000, "total_tokens": 11000}}


class KimiServer(OpenAIServer):
    """Moonshot Batch API: OpenAI-compatible files/batches, Chat Completions result bodies."""

    def __init__(self, t):
        self.files, self.batches, self.polls = {}, {}, {}
        t.route("POST", r"api\.moonshot\.ai/v1/files$", self.upload)
        t.route("POST", r"api\.moonshot\.ai/v1/batches$", self.create)
        t.route("GET", r"api\.moonshot\.ai/v1/batches/", self.get)
        t.route("GET", r"api\.moonshot\.ai/v1/files/[^/]+/content$", self.content)

    def create(self, url, h, body):
        d = json.loads(body)
        assert d["endpoint"] == "/v1/chat/completions" and d["completion_window"] == "24h"
        bid = f"batch_{len(self.batches) + 1}"
        self.batches[bid] = self.files[d["input_file_id"]]
        self.polls[bid] = 0
        return ok({"id": bid, "status": "validating"})

    def content(self, url, h, body):
        fid = url.split("/")[-2]
        bid = fid.split("-", 2)[2]
        out = []
        for r in self.batches[bid]:
            b = behaviour(r["custom_id"])
            if fid.startswith("file-err") and b == "error":
                out.append({"custom_id": r["custom_id"], "response": {"status_code": 500, "body": None},
                            "error": {"code": "server_error", "message": "bad"}})
            elif fid.startswith("file-out") and b != "error":
                text = GOOD if b == "good" else "I'm sorry, I can't help with that."
                out.append({"custom_id": r["custom_id"], "response": {"status_code": 200, "body": chat_completion(text)},
                            "error": None})
        return ok("\n".join(json.dumps(x) for x in out).encode())


class DeepSeekServer:
    """Synchronous chat completions. behaviour() 'error' -> HTTP 500; `status_override` forces a status."""

    def __init__(self, t):
        self.requests = []
        self.status_override = None
        t.route("POST", r"api\.deepseek\.com/chat/completions$", self.chat)

    def chat(self, url, h, body):
        if self.status_override:
            return ok({"error": {"message": "Insufficient Balance"}}, status=self.status_override)
        d = json.loads(body)
        self.requests.append(d)
        user = d["messages"][1]["content"]
        idx = user.split("hello ")[1].split("\n")[0]
        cid_hint = f"t{int(idx):03d}"
        # the repeat is not in the body; alternate by call count per transcript to emulate r1/r2
        n = sum(1 for r in self.requests if r["messages"][1]["content"] == user)
        b = behaviour(f"{cid_hint}-x-r{n}")
        if b == "error":
            return ok({"error": {"message": "server busy"}}, status=500)
        text = GOOD if b == "good" else "I'm sorry, I can't help with that."
        return ok(chat_completion(text))
