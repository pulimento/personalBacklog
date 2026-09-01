from __future__ import annotations

import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from personal_backlog.server import create_server
from personal_backlog.storage import init_backlog


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.backlog = init_backlog(Path(self.temporary.name) / "backlog")
        self.server = create_server(self.backlog, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1])

    def tearDown(self) -> None:
        self.connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, method: str, path: str, payload: dict | None = None):
        body = json.dumps(payload) if payload is not None else None
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        self.connection.request(method, path, body=body, headers=headers)
        response = self.connection.getresponse()
        data = json.loads(response.read())
        return response.status, data

    def test_crud_api_and_stale_revision(self) -> None:
        status, created = self.request(
            "POST",
            "/api/tasks",
            {"title": "From browser", "priority": 2, "release": "next", "tags": ["bug", "web"]},
        )
        self.assertEqual(status, 201)
        self.assertEqual(created["tags"], ["bug", "web"])
        stale_revision = created["revision"]

        status, updated = self.request(
            "PUT",
            "/api/tasks/T0001",
            {"title": "Updated", "state": "done", "tags": ["bug"], "revision": stale_revision},
        )
        self.assertEqual(status, 200)
        self.assertIsNotNone(updated["done"])
        self.assertEqual(updated["tags"], ["bug"])

        status, error = self.request(
            "PUT",
            "/api/tasks/T0001",
            {"title": "Stale", "revision": stale_revision},
        )
        self.assertEqual(status, 409)
        self.assertIn("changed since", error["error"])

    def test_static_assets_and_cross_origin_protection(self) -> None:
        self.connection.request("GET", "/")
        response = self.connection.getresponse()
        self.assertEqual(response.status, 200)
        content = response.read()
        self.assertIn(b"PERSONAL BACKLOG", content)
        self.assertIn(b"Board", content)
        self.assertIn(b"Editor", content)

        self.connection.request("GET", "/task-detail.js")
        response = self.connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertIn(b"PersonalBacklogTaskDetail", response.read())

        status, meta = self.request("GET", "/api/meta")
        self.assertEqual((status, meta["current_release"]), (200, None))
        self.assertFalse(meta["read_only"])

        body = json.dumps({"title": "Forbidden"})
        self.connection.request(
            "POST",
            "/api/tasks",
            body=body,
            headers={"Content-Type": "application/json", "Origin": "https://example.com"},
        )
        response = self.connection.getresponse()
        self.assertEqual(response.status, 403)
        response.read()

        self.connection.request(
            "POST",
            "/api/tasks",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Origin": "http://127.0.0.1:9999",
            },
        )
        response = self.connection.getresponse()
        self.assertEqual(response.status, 403)
        response.read()

    def test_read_only_server_mode(self) -> None:
        ro_server = create_server(self.backlog, port=0, read_only=True)
        thread = threading.Thread(target=ro_server.serve_forever, daemon=True)
        thread.start()
        conn = http.client.HTTPConnection("127.0.0.1", ro_server.server_address[1])
        try:
            conn.request("GET", "/api/meta")
            meta = json.loads(conn.getresponse().read())
            self.assertTrue(meta["read_only"])

            conn.request("POST", "/api/tasks", body=json.dumps({"title": "Test"}), headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 405)
            self.assertEqual(resp.getheader("Allow"), "GET")
            data = json.loads(resp.read())
            self.assertIn("read-only mode", data["error"])
        finally:
            conn.close()
            ro_server.shutdown()
            ro_server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
