#!/usr/bin/env python3
"""SinIceStir anonymous suggestion box backend.

Tiny stdlib-only HTTP server that accepts POST /api/suggestion with a JSON
body (or form-urlencoded). Appends each submission as one line of JSON to
suggestions.jsonl. Captures NO identifying information — no IP, no headers,
no user-agent. Caller's name field is optional and only stored if the user
explicitly provided it.

Listens on 127.0.0.1:8090. Caddy reverse-proxies /api/suggestion to it.
"""
import datetime
import fcntl
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

LOG_DIR = "/home/work/suggestion-box/data"
LOG_FILE = os.path.join(LOG_DIR, "suggestions.jsonl")
MAX_BODY = 100_000  # 100 KB max request body
MAX_MSG = 5000
MAX_NAME = 100
MAX_CATEGORY = 50

ALLOWED_CATEGORIES = {
    "", "operations", "product", "service", "safety", "culture", "other"
}


class SuggestionHandler(BaseHTTPRequestHandler):

    # ----- silence default logging (we don't want IPs in our logs) -----
    def log_message(self, format, *args):
        pass

    def address_string(self):
        return "anon"

    # ----- helpers -----
    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, status, msg):
        body = msg.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ----- routes -----
    def do_GET(self):
        if self.path == "/api/suggestion/health":
            return self._json(200, {"ok": True})
        return self._text(404, "not found")

    def do_POST(self):
        if self.path != "/api/suggestion":
            return self._text(404, "not found")

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._text(400, "bad content length")
        if length <= 0:
            return self._text(400, "empty body")
        if length > MAX_BODY:
            return self._text(413, "too large")

        raw = self.rfile.read(length)
        try:
            body_text = raw.decode("utf-8", errors="replace")
        except Exception:
            return self._text(400, "bad encoding")

        # accept JSON or form-urlencoded
        ctype = (self.headers.get("Content-Type") or "").lower()
        data = {}
        if "application/json" in ctype:
            try:
                data = json.loads(body_text)
            except Exception:
                return self._text(400, "bad json")
        else:
            try:
                parsed = parse_qs(body_text, keep_blank_values=True)
                data = {k: v[0] if v else "" for k, v in parsed.items()}
            except Exception:
                return self._text(400, "bad form data")

        if not isinstance(data, dict):
            return self._text(400, "expected object")

        message = (str(data.get("message", ""))).strip()
        if not message:
            return self._text(400, "message required")
        if len(message) > MAX_MSG:
            message = message[:MAX_MSG]

        category = (str(data.get("category", ""))).strip().lower()
        if category not in ALLOWED_CATEGORIES:
            category = "other"
        category = category[:MAX_CATEGORY]

        name = (str(data.get("name", ""))).strip()[:MAX_NAME] or None

        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "category": category,
            "message": message,
            "name": name,
        }

        try:
            os.makedirs(LOG_DIR, mode=0o750, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            sys.stderr.write(f"write error: {e}\n")
            return self._text(500, "store failed")

        return self._json(200, {"ok": True})


def main():
    bind = ("127.0.0.1", 8090)
    srv = HTTPServer(bind, SuggestionHandler)
    sys.stderr.write(f"sin-suggestion-box listening on {bind[0]}:{bind[1]}\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
