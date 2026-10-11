import os
import unittest
import weakref
from types import SimpleNamespace
from unittest.mock import patch

from ai import model


class _FakeChat:
    def __init__(self, client):
        self._client = weakref.ref(client)
        self.messages = []

    def send_message(self, message):
        client = self._client()
        if client is None or client.closed:
            raise RuntimeError("Cannot send a request, as the client is closed.")
        self.messages.append(message)
        return SimpleNamespace(text=f"response: {message}")


class _FakeChats:
    def __init__(self, client):
        self._client = client
        self.create_calls = []
        self.created_chats = []

    def create(self, model):
        self.create_calls.append(model)
        self.chat = _FakeChat(self._client)
        self.created_chats.append(self.chat)
        return self.chat


class _FakeClient:
    instances = []

    def __init__(self, api_key):
        self.api_key = api_key
        self.closed = False
        self.close_calls = 0
        self.chats = _FakeChats(self)
        self.instances.append(self)

    def close(self):
        self.close_calls += 1
        self.closed = True


class GeminiClientLifecycleTests(unittest.TestCase):
    def setUp(self):
        model.close_gemini()
        _FakeClient.instances = []
        self.environment = patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
        self.environment.start()
        self.client_factory = patch.object(model.genai, "Client", _FakeClient)
        self.client_factory.start()
        self.addCleanup(self.client_factory.stop)
        self.addCleanup(self.environment.stop)
        self.addCleanup(model.close_gemini)

    def test_first_and_consecutive_requests_retain_one_live_client(self):
        self.assertEqual(model.ask_gemini("first"), "response: first")
        self.assertEqual(model.ask_gemini("second"), "response: second")

        self.assertEqual(len(_FakeClient.instances), 1)
        client = _FakeClient.instances[0]
        self.assertFalse(client.closed)
        self.assertEqual(client.chats.create_calls, ["gemini-3.6-flash"])
        self.assertEqual(client.chats.chat.messages, ["first", "second"])

    def test_conversations_use_separate_sdk_chat_histories(self):
        model.ask_gemini("first conversation", conversation_id="first")
        model.ask_gemini("second conversation", conversation_id="second")
        model.ask_gemini("back to first", conversation_id="first")

        client = _FakeClient.instances[0]
        self.assertEqual(len(_FakeClient.instances), 1)
        self.assertEqual(len(client.chats.created_chats), 2)
        self.assertEqual(
            client.chats.created_chats[0].messages,
            ["first conversation", "back to first"],
        )
        self.assertEqual(
            client.chats.created_chats[1].messages,
            ["second conversation"],
        )

    def test_shutdown_closes_client_once_and_later_request_uses_new_client(self):
        model.ask_gemini("before shutdown")
        first_client = _FakeClient.instances[0]

        model.close_gemini()
        model.close_gemini()

        self.assertTrue(first_client.closed)
        self.assertEqual(first_client.close_calls, 1)
        self.assertEqual(model._conversation_chats, {})
        self.assertEqual(model.ask_gemini("after shutdown"), "response: after shutdown")
        self.assertEqual(len(_FakeClient.instances), 2)
        self.assertIsNot(_FakeClient.instances[1], first_client)

    def test_closed_cached_client_is_discarded_and_recreated_on_next_request(self):
        model.ask_gemini("initial request")
        first_client = _FakeClient.instances[0]
        first_client.close()

        with self.assertRaisesRegex(RuntimeError, "client is closed"):
            model.ask_gemini("request on the closed client")

        self.assertIsNone(model._client)
        self.assertIsNone(model._chat)
        self.assertEqual(model._conversation_chats, {})
        self.assertEqual(
            model.ask_gemini("request after recovery"),
            "response: request after recovery",
        )
        self.assertEqual(len(_FakeClient.instances), 2)

    def test_failed_chat_creation_closes_unpublished_client(self):
        def fail_chat_creation(client, model):
            raise RuntimeError("chat initialization failed")

        with patch.object(_FakeChats, "create", fail_chat_creation):
            with self.assertRaisesRegex(RuntimeError, "chat initialization failed"):
                model.ask_gemini("first")

        self.assertEqual(len(_FakeClient.instances), 1)
        self.assertTrue(_FakeClient.instances[0].closed)
        self.assertEqual(_FakeClient.instances[0].close_calls, 1)
        self.assertIsNone(model._client)
        self.assertIsNone(model._chat)


if __name__ == "__main__":
    unittest.main()
