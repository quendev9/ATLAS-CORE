import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from memory import conversations


class HUDConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.storage_patch = patch.object(
            conversations,
            "CONVERSATIONS_FILE",
            Path(self.temp_dir.name) / "conversations.json",
        )
        self.storage_patch.start()
        self.addCleanup(self.storage_patch.stop)

        self.existing = conversations.create_conversation(
            "Existing history",
            project="ATLAS",
        )
        conversations.add_message(
            self.existing["id"],
            "user",
            "Keep this history.",
        )

        from ui import server

        self.server_module = server
        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            server.LewisHandler,
        )
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"

    def _stop_server(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _request(self, path, payload=None):
        request = Request(
            self.base_url + path,
            data=(
                json.dumps(payload).encode("utf-8")
                if payload is not None
                else None
            ),
            headers={"Content-Type": "application/json"},
            method="POST" if payload is not None else "GET",
        )
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_create_and_reopen_conversations_preserves_history(self):
        status, created_payload = self._request("/api/conversations", {})
        created = created_payload["conversation"]

        self.assertEqual(status, 201)
        self.assertEqual(
            conversations.get_active_conversation_id(),
            created["id"],
        )
        self.assertEqual(
            self.server_module.lewis.active_conversation_id,
            created["id"],
        )

        _, list_payload = self._request("/api/conversations")
        self.assertEqual(
            {item["id"] for item in list_payload["conversations"]},
            {self.existing["id"], created["id"]},
        )

        _, selected_payload = self._request(
            "/api/conversations/select",
            {"id": self.existing["id"]},
        )
        self.assertEqual(
            selected_payload["conversation"]["messages"][0]["content"],
            "Keep this history.",
        )
        self.assertEqual(
            conversations.get_active_conversation_id(),
            self.existing["id"],
        )
        self.assertEqual(
            self.server_module.lewis.active_conversation_id,
            self.existing["id"],
        )

        _, history_payload = self._request(
            f"/api/conversations/{self.existing['id']}"
        )
        self.assertEqual(
            history_payload["conversation"]["messages"][0]["content"],
            "Keep this history.",
        )


if __name__ == "__main__":
    unittest.main()
