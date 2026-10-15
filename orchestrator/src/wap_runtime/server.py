"""Service HTTP du runtime : `GET /health`."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wap_runtime import __version__


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        corps = json.dumps({"status": "ok", "version": __version__}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, format, *args):
        pass


def creer_serveur(hote: str, port: int) -> ThreadingHTTPServer:
    """Serveur prêt à `serve_forever()` ; `port=0` choisit un port libre."""
    return ThreadingHTTPServer((hote, port), _Handler)
