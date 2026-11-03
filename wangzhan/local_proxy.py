import argparse
import http.server
import mimetypes
import os
import posixpath
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class BaiqipuHandler(http.server.BaseHTTPRequestHandler):
    frontend_dir: Path
    backend_url: str

    def do_GET(self):
        self.route_request()

    def do_HEAD(self):
        self.route_request(send_body=False)

    def do_POST(self):
        self.proxy_to_backend()

    def do_PUT(self):
        self.proxy_to_backend()

    def do_PATCH(self):
        self.proxy_to_backend()

    def do_DELETE(self):
        self.proxy_to_backend()

    def do_OPTIONS(self):
        self.proxy_to_backend()

    def route_request(self, send_body=True):
        parsed = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parsed.path)

        if (
            path.startswith("/api/")
            or path.startswith("/generated/")
            or path.startswith("/assets/video_backgrounds/")
        ):
            self.proxy_to_backend(send_body=send_body)
            return

        self.serve_frontend(path, send_body=send_body)

    def serve_frontend(self, request_path, send_body=True):
        safe_path = posixpath.normpath(request_path.lstrip("/"))
        if safe_path in ("", "."):
            safe_path = "index.html"

        candidate = (self.frontend_dir / safe_path).resolve()
        frontend_root = self.frontend_dir.resolve()

        if not str(candidate).startswith(str(frontend_root)):
            self.send_error(403)
            return

        if candidate.is_dir():
            candidate = candidate / "index.html"

        if not candidate.exists():
            if request_path.startswith("/assets/") or request_path.startswith("/images/"):
                self.send_error(404)
                return
            candidate = frontend_root / "index.html"

        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        if candidate.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif candidate.suffix in {".html", ".css", ".svg", ".json", ".xml", ".txt"}:
            charset_types = {
                ".html": "text/html",
                ".css": "text/css",
                ".svg": "image/svg+xml",
                ".json": "application/json",
                ".xml": "application/xml",
                ".txt": "text/plain",
            }
            content_type = f"{charset_types[candidate.suffix]}; charset=utf-8"

        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def proxy_to_backend(self, send_body=True):
        body = None
        content_length = self.headers.get("Content-Length")
        if content_length:
            body = self.rfile.read(int(content_length))

        target_url = self.backend_url.rstrip("/") + self.path
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "host"
        }

        request = urllib.request.Request(
            target_url,
            data=body,
            headers=headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = b"" if self.command == "HEAD" or not send_body else response.read()
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in HOP_BY_HOP_HEADERS:
                        self.send_header(key, value)
                self.end_headers()
                if data:
                    self.wfile.write(data)
        except urllib.error.HTTPError as error:
            data = error.read()
            self.send_response(error.code)
            for key, value in error.headers.items():
                if key.lower() not in HOP_BY_HOP_HEADERS:
                    self.send_header(key, value)
            self.end_headers()
            if send_body and data:
                self.wfile.write(data)
        except Exception as error:
            message = f"Backend proxy failed: {error}".encode("utf-8", errors="replace")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            if send_body:
                self.wfile.write(message)

    def log_message(self, format, *args):
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", required=True)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    frontend = Path(args.frontend).resolve()
    if not (frontend / "index.html").exists():
        raise SystemExit(f"Frontend index.html not found: {frontend}")

    BaiqipuHandler.frontend_dir = frontend
    BaiqipuHandler.backend_url = args.backend

    server = http.server.ThreadingHTTPServer((args.host, args.port), BaiqipuHandler)
    print(f"Serving Baiqipu at http://{args.host}:{args.port}")
    print(f"Frontend: {frontend}")
    print(f"Backend:  {args.backend}")
    server.serve_forever()


if __name__ == "__main__":
    main()
