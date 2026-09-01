from __future__ import annotations

import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from personal_backlog.board import create_board_server
from personal_backlog.storage import create_task, init_backlog


class BoardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.backlog = init_backlog(Path(self.temporary.name) / "sample-project" / "backlog")
        create_task(
            self.backlog,
            title="Visible on the board",
            release="next",
            priority=1,
            size="S",
            tags=["bug", "web"],
        )
        self.server = create_board_server(self.backlog, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1])

    def tearDown(self) -> None:
        self.connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def response(self, method: str, path: str) -> tuple[int, dict | bytes, dict[str, str]]:
        self.connection.request(method, path)
        response = self.connection.getresponse()
        content_type = response.getheader("Content-Type", "")
        headers = {key: value for key, value in response.getheaders()}
        body = response.read()
        payload = json.loads(body) if "application/json" in content_type else body
        return response.status, payload, headers

    def test_board_assets_and_task_api(self) -> None:
        status, page, _ = self.response("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Todo", page)
        self.assertIn(b"In progress", page)
        self.assertIn(b"Done", page)

        status, tasks, _ = self.response("GET", "/api/tasks")
        self.assertEqual(status, 200)
        self.assertEqual(tasks[0]["title"], "Visible on the board")
        self.assertNotIn("body", tasks[0])
        self.assertEqual(tasks[0]["tags"], ["bug", "web"])

        status, task, _ = self.response("GET", "/api/tasks/T0001")
        self.assertEqual(status, 200)
        self.assertEqual(task["id"], "T0001")
        self.assertEqual(task["body"], "")

        status, meta, _ = self.response("GET", "/api/meta")
        self.assertEqual(status, 200)
        self.assertEqual(meta["project"], "sample-project")
        self.assertEqual(meta["current_release"], "next")

        self.connection.request("GET", "/task-detail.js")
        response = self.connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertIn(b"PersonalBacklogTaskDetail", response.read())

    def test_board_rejects_mutations(self) -> None:
        status, error, headers = self.response("POST", "/api/tasks")
        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "GET")
        self.assertEqual(error["error"], "the web app is running in read-only mode")

        status, tasks, _ = self.response("GET", "/api/tasks")
        self.assertEqual(status, 200)
        self.assertEqual(len(tasks), 1)

    def test_board_rejects_non_local_host(self) -> None:
        self.connection.request("GET", "/api/tasks", headers={"Host": "example.com"})
        response = self.connection.getresponse()
        self.assertEqual(response.status, 400)
        response.read()


if __name__ == "__main__":
    unittest.main()
