import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
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
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(
                    response.read().decode("utf-8")
                )
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

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

    def test_rename_persists_title_without_changing_active_history(self):
        conversations.set_active_conversation(self.existing["id"])
        self.server_module.lewis.active_conversation_id = self.existing["id"]
        original = conversations.get_conversation(self.existing["id"])

        status, payload = self._request(
            "/api/conversations/rename",
            {"id": self.existing["id"], "title": "  Renamed history  "},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["conversation"]["title"], "Renamed history")
        self.assertEqual(
            payload["conversation"]["messages"],
            original["messages"],
        )
        self.assertEqual(
            conversations.get_active_conversation_id(),
            self.existing["id"],
        )
        self.assertEqual(
            self.server_module.lewis.active_conversation_id,
            self.existing["id"],
        )

        _, list_payload = self._request("/api/conversations")
        listed = next(
            item
            for item in list_payload["conversations"]
            if item["id"] == self.existing["id"]
        )
        self.assertEqual(listed["title"], "Renamed history")

    def test_rename_rejects_empty_oversized_and_unknown_titles(self):
        for title in ("   ", "x" * 121):
            status, payload = self._request(
                "/api/conversations/rename",
                {"id": self.existing["id"], "title": title},
            )
            self.assertEqual(status, 400)
            self.assertIn("error", payload)

        status, payload = self._request(
            "/api/conversations/rename",
            {"id": "missing-conversation", "title": "Valid title"},
        )
        self.assertEqual(status, 404)
        self.assertIn("error", payload)
        self.assertEqual(
            conversations.get_conversation(self.existing["id"])["title"],
            "Existing history",
        )

    def test_deleting_inactive_conversation_preserves_active_history(self):
        inactive = conversations.create_conversation(
            "Inactive history",
            project="ATLAS",
        )
        conversations.add_message(
            inactive["id"],
            "user",
            "This history will be deleted.",
        )
        conversations.set_active_conversation(self.existing["id"])
        self.server_module.lewis.active_conversation_id = self.existing["id"]
        active_history = conversations.get_conversation(self.existing["id"])[
            "messages"
        ]

        status, payload = self._request(
            "/api/conversations/delete",
            {"id": inactive["id"]},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["deleted_id"], inactive["id"])
        self.assertEqual(
            payload["active_conversation_id"],
            self.existing["id"],
        )
        self.assertIsNone(conversations.get_conversation(inactive["id"]))
        self.assertEqual(
            conversations.get_conversation(self.existing["id"])["messages"],
            active_history,
        )
        self.assertEqual(
            self.server_module.lewis.active_conversation_id,
            self.existing["id"],
        )

    def test_deleting_active_conversation_selects_remaining_or_empty_state(self):
        other = conversations.create_conversation(
            "Other conversation",
            project="ATLAS",
        )
        self.server_module.lewis.active_conversation_id = other["id"]

        status, payload = self._request(
            "/api/conversations/delete",
            {"id": other["id"]},
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            payload["active_conversation_id"],
            self.existing["id"],
        )
        self.assertEqual(
            self.server_module.lewis.active_conversation_id,
            self.existing["id"],
        )

        status, payload = self._request(
            "/api/conversations/delete",
            {"id": self.existing["id"]},
        )
        self.assertEqual(status, 200)
        self.assertIsNone(payload["active_conversation_id"])
        self.assertIsNone(conversations.get_active_conversation_id())
        self.assertIsNone(self.server_module.lewis.active_conversation_id)
        self.assertIsNone(conversations.get_conversation(self.existing["id"]))


if __name__ == "__main__":
    unittest.main()
