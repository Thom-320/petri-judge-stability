"""Minimal HTTP transport (stdlib) so runners can be tested with a fake transport and no network.

Headers are never logged. Error messages are built only from the status code and a truncated
response body, and pass through `redact()` before they are stored or printed.
"""
import json
import os
import re
import urllib.error
import urllib.request

KEY_ENV = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "MOONSHOT_API_KEY", "DEEPSEEK_API_KEY")


class HTTPError(Exception):
    def __init__(self, status, body):
        self.status = status
        self.body = redact(body[:500] if isinstance(body, str) else str(body)[:500])
        super().__init__(f"HTTP {status}: {self.body}")


def redact(text):
    """Remove the value of any API key env var (and bearer tokens) from a string."""
    if not text:
        return text
    for name in KEY_ENV:
        val = os.environ.get(name)
        if val and len(val) >= 8:
            text = text.replace(val, "[REDACTED]")
    return re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]+", r"\1[REDACTED]", text)


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.body = body

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    def text(self):
        return self.body.decode("utf-8")


class UrllibTransport:
    def __init__(self, timeout=600):
        self.timeout = timeout

    def request(self, method, url, headers=None, body=None):
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return Response(r.status, dict(r.headers), r.read())
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            raise HTTPError(e.code, raw) from None


def check(resp):
    if not 200 <= resp.status < 300:
        raise HTTPError(resp.status, resp.body.decode("utf-8", "replace"))
    return resp


def multipart(fields, files):
    """Encode multipart/form-data. files: {name: (filename, bytes, content_type)}."""
    boundary = "----petriv2" + os.urandom(12).hex()
    out = []
    for k, v in fields.items():
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (fname, data, ctype) in files.items():
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                   f"Content-Type: {ctype}\r\n\r\n".encode() + data + b"\r\n")
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"
