"""Health endpoint for the Pragati 2.0 prototype. No database calls."""
import json
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(
            {"status": "ok", "version": os.environ.get("VERCEL_GIT_COMMIT_SHA", "dev")}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
