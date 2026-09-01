from __future__ import annotations

import errno
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
import threading
from typing import Any
from urllib.parse import unquote, urlsplit
import webbrowser

from personal_backlog import __version__
from personal_backlog.model import BacklogError, ConflictError, NotFoundError
from personal_backlog.ports import port_conflict_details
from personal_backlog.storage import (
    MISSING,
    create_task,
    current_release,
    get_task,
    list_tasks,
    task_revision,
    update_task,
)


MAX_REQUEST_BYTES = 1_000_000
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/task-detail.js": ("task-detail.js", "text/javascript; charset=utf-8"),
    "/task-detail.css": ("task-detail.css", "text/css; charset=utf-8"),
}


class BacklogHandler(BaseHTTPRequestHandler):
    server_version = f"PersonalBacklog/{__version__}"

    def __init__(self, *args: Any, backlog_dir: Path, read_only: bool = False, **kwargs: Any) -> None:
        self.backlog_dir = backlog_dir
        self.read_only = read_only
        super().__init__(*args, **kwargs)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def do_GET(self) -> None:
        if not self._valid_host():
            self._json_error(HTTPStatus.BAD_REQUEST, "invalid Host header")
            return
        path = urlsplit(self.path).path
        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            package = "personal_backlog.task_web" if filename.startswith("task-detail") else "personal_backlog.web"
            content = files(package).joinpath(filename).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/api/meta":
            self._send_json(
                HTTPStatus.OK,
                {
                    "backlog": str(self.backlog_dir),
                    "project": self.backlog_dir.parent.name,
                    "version": __version__,
                    "current_release": current_release(self.backlog_dir),
                    "read_only": self.read_only,
                },
            )
            return
        if path == "/api/tasks":
            try:
                tasks = [task.as_dict(include_body=False) for task in list_tasks(self.backlog_dir)]
                self._send_json(HTTPStatus.OK, tasks)
            except BacklogError as exc:
                self._json_error(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))
            return
        if path.startswith("/api/tasks/"):
            task_id = unquote(path.removeprefix("/api/tasks/"))
            try:
                task = get_task(self.backlog_dir, task_id)
                data = task.as_dict()
                data["revision"] = task_revision(self.backlog_dir, task.id)
                self._send_json(HTTPStatus.OK, data)
            except NotFoundError as exc:
                self._json_error(HTTPStatus.NOT_FOUND, str(exc))
            except BacklogError as exc:
                self._json_error(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))
            return
        self._json_error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
        if self.read_only:
            self._send_read_only()
            return
        if not self._valid_mutation_request():
            return
        if urlsplit(self.path).path != "/api/tasks":
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            payload = self._read_json()
            self._reject_unknown(payload, {"title", "release", "priority", "size", "state", "tags", "body"})
            if "title" not in payload:
                raise ValueError("title is required")
            task = create_task(
                self.backlog_dir,
                title=payload["title"],
                release=payload.get("release"),
                priority=payload.get("priority", 3),
                size=payload.get("size"),
                state=payload.get("state", "todo"),
                tags=payload.get("tags"),
                body=payload.get("body", ""),
            )
            data = task.as_dict()
            data["revision"] = task_revision(self.backlog_dir, task.id)
            self._send_json(HTTPStatus.CREATED, data)
        except (ValueError, TypeError, BacklogError) as exc:
            self._json_error(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    def do_PUT(self) -> None:
        if self.read_only:
            self._send_read_only()
            return
        if not self._valid_mutation_request():
            return
        path = urlsplit(self.path).path
        if not path.startswith("/api/tasks/"):
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return
        task_id = unquote(path.removeprefix("/api/tasks/"))
        try:
            payload = self._read_json()
            allowed = {"title", "release", "priority", "size", "state", "tags", "body", "revision"}
            self._reject_unknown(payload, allowed)
            revision = payload.pop("revision", None)
            if not revision:
                raise ValueError("revision is required; reload the task")
            changes = {
                key: payload.get(key, MISSING)
                for key in ("title", "release", "priority", "size", "state", "tags", "body")
            }
            if all(value is MISSING for value in changes.values()):
                raise ValueError("nothing to update")
            task = update_task(
                self.backlog_dir,
                task_id,
                expected_revision=revision,
                **changes,
            )
            data = task.as_dict()
            data["revision"] = task_revision(self.backlog_dir, task.id)
            self._send_json(HTTPStatus.OK, data)
        except ConflictError as exc:
            self._json_error(HTTPStatus.CONFLICT, str(exc))
        except NotFoundError as exc:
            self._json_error(HTTPStatus.NOT_FOUND, str(exc))
        except (ValueError, TypeError, BacklogError) as exc:
            self._json_error(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    def do_PATCH(self) -> None:
        self._send_read_only() if self.read_only else self._json_error(HTTPStatus.NOT_FOUND, "not found")

    def do_DELETE(self) -> None:
        self._send_read_only() if self.read_only else self._json_error(HTTPStatus.NOT_FOUND, "not found")

    def _send_read_only(self) -> None:
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET")
        content = json.dumps({"error": "the web app is running in read-only mode"}).encode("utf-8")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _valid_host(self) -> bool:
        host = self.headers.get("Host", "")
        hostname = urlsplit(f"//{host}").hostname
        return hostname in {"127.0.0.1", "localhost"}

    def _valid_mutation_request(self) -> bool:
        if not self._valid_host():
            self._json_error(HTTPStatus.BAD_REQUEST, "invalid Host header")
            return False
        origin = self.headers.get("Origin")
        if origin:
            origin_parts = urlsplit(origin)
            request_host = self.headers.get("Host", "")
            if origin_parts.scheme != "http" or origin_parts.netloc.lower() != request_host.lower():
                self._json_error(HTTPStatus.FORBIDDEN, "cross-origin writes are not allowed")
                return False
        if self.headers.get_content_type() != "application/json":
            self._json_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
            return False
        return True

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("request body is empty or too large")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    @staticmethod
    def _reject_unknown(payload: dict[str, Any], allowed: set[str]) -> None:
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError(f"unknown fields: {', '.join(unknown)}")

    def _send_json(self, status: HTTPStatus, payload: object) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _json_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def create_server(backlog_dir: Path, port: int = 8765, read_only: bool = False) -> ThreadingHTTPServer:
    if not 0 <= port <= 65535:
        raise BacklogError("port must be between 0 and 65535")
    handler = partial(BacklogHandler, backlog_dir=backlog_dir, read_only=read_only)
    try:
        return ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        details = port_conflict_details(port) if exc.errno == errno.EADDRINUSE else ""
        raise BacklogError(f"could not start web app on port {port}: {exc}{details}") from exc


def serve(backlog_dir: Path, *, port: int = 8765, open_browser: bool = True, read_only: bool = False) -> None:
    server = create_server(backlog_dir, port, read_only=read_only)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    mode_text = " (read-only)" if read_only else ""
    print(f"Serving {backlog_dir}{mode_text}")
    print(f"Open {url} (Ctrl-C to stop)")
    if open_browser:
        threading.Timer(0.2, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
