import io
import json
import os
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from ai import model


def _success_response(content):
    return io.BytesIO(json.dumps({
        "choices": [{"message": {"content": content}}],
    }).encode("utf-8"))


class GroqProviderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.key_index = patch.object(model, "_groq_next_key_index", 0)
        self.key_index.start()
        self.addCleanup(self.key_index.stop)
        self.selection = patch.object(model, "_selected_ai_model", None)
        self.selection.start()
        self.addCleanup(self.selection.stop)

    def test_keys_are_used_round_robin(self):
        os.environ["GROQ_API_KEYS"] = "first-key, second-key"

        with patch.object(
            model,
            "urlopen",
            side_effect=[
                _success_response("Groq reply"),
                _success_response("Groq reply"),
            ],
        ) as request:
            self.assertEqual(model.ask_groq("hello"), "Groq reply")
            self.assertEqual(
                model.ask_groq("again"),
                "Groq reply",
            )

        self.assertEqual(
            [
                call.args[0].get_header("Authorization")
                for call in request.call_args_list
            ],
            ["Bearer first-key", "Bearer second-key"],
        )
        self.assertEqual(
            json.loads(request.call_args_list[0].args[0].data)["model"],
            "openai/gpt-oss-20b",
        )
        self.assertEqual(
            request.call_args_list[0].args[0].full_url,
            model.GROQ_API_URL,
        )
        self.assertEqual(
            json.loads(request.call_args_list[0].args[0].data)["messages"],
            [{"role": "user", "content": "hello"}],
        )

    def test_rate_limited_key_retries_with_next_key(self):
        os.environ["GROQ_API_KEYS"] = "first-key, second-key"
        limited_response = io.BytesIO(
            b'{"error":{"message":"Rate limit exceeded"}}'
        )
        rate_limit = HTTPError(
            model.GROQ_API_URL,
            429,
            "Too Many Requests",
            {},
            limited_response,
        )

        with patch.object(
            model,
            "urlopen",
            side_effect=[rate_limit, _success_response("Recovered")],
        ) as request:
            self.assertEqual(model.ask_groq("hello"), "Recovered")

        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            request.call_args_list[1].args[0].get_header("Authorization"),
            "Bearer second-key",
        )

    def test_http_error_detail_is_kept_and_configured_key_is_redacted(self):
        api_key = "local-test-groq-secret"
        os.environ["GROQ_API_KEY"] = api_key
        response = io.BytesIO(json.dumps({
            "error": {
                "message": f"Workspace access denied for {api_key}.",
                "type": "permission_error",
            },
        }).encode("utf-8"))
        permission_error = HTTPError(
            model.GROQ_API_URL,
            403,
            "Forbidden",
            {},
            response,
        )

        with patch.object(model, "urlopen", side_effect=permission_error):
            with self.assertRaises(model.GroqAPIError) as raised:
                model.ask_groq("hello")

        self.assertEqual(raised.exception.status_code, 403)
        self.assertIn("Workspace access denied", str(raised.exception))
        self.assertIn("permission_error", str(raised.exception))
        self.assertNotIn(api_key, str(raised.exception))

    def test_non_json_error_body_is_preserved_and_configured_key_redacted(self):
        api_key = "local-test-groq-secret"
        os.environ["GROQ_API_KEY"] = api_key
        permission_error = HTTPError(
            model.GROQ_API_URL,
            403,
            "Forbidden",
            {},
            io.BytesIO(f"Request denied for {api_key}".encode("utf-8")),
        )

        with patch.object(model, "urlopen", side_effect=permission_error):
            with self.assertRaises(model.GroqAPIError) as raised:
                model.ask_groq("hello")

        self.assertIn("Request denied for [REDACTED]", str(raised.exception))
        self.assertNotIn(api_key, str(raised.exception))

    def test_http_error_statuses_preserve_provider_messages(self):
        for status_code in (401, 403, 404, 429, 503):
            with self.subTest(status_code=status_code):
                os.environ["GROQ_API_KEY"] = "test-key"
                response = io.BytesIO(json.dumps({
                    "error": {
                        "message": f"Provider returned {status_code}.",
                        "type": "test_error",
                    },
                }).encode("utf-8"))
                api_error = HTTPError(
                    model.GROQ_API_URL,
                    status_code,
                    "Provider error",
                    {},
                    response,
                )

                with patch.object(model, "urlopen", side_effect=api_error):
                    with self.assertRaises(model.GroqAPIError) as raised:
                        model.ask_groq("hello")

                self.assertEqual(
                    raised.exception.status_code,
                    status_code,
                )
                self.assertIn(
                    f"Provider returned {status_code}.",
                    str(raised.exception),
                )
                self.assertIn("test_error", str(raised.exception))

    def test_missing_key_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEYS"):
            model.ask_groq("hello")

    def test_provider_info_reports_groq_configuration(self):
        os.environ["AI_PROVIDER"] = "groq"
        os.environ["GROQ_API_KEYS"] = "first-key,second-key"
        os.environ["GROQ_MODEL"] = "llama-test-model"

        self.assertEqual(
            model.get_ai_provider_info(),
            {
                "provider": "Groq",
                "model": "llama-test-model",
                "configured": True,
                "selection": {
                    "provider": "groq",
                    "model": "llama-test-model",
                },
            },
        )

    def test_manual_selection_dispatches_to_the_selected_provider_and_model(self):
        os.environ["GEMINI_API_KEY"] = "gemini-test-key"
        os.environ["GROQ_API_KEY"] = "groq-test-key"
        os.environ["GEMINI_MODEL"] = "gemini-test-model"
        os.environ["GROQ_MODEL"] = "openai/gpt-oss-20b"

        with (
            patch.object(model, "ask_gemini", return_value="Gemini") as gemini,
            patch.object(model, "ask_groq", return_value="Groq") as groq,
        ):
            model.set_ai_selection("gemini", "gemini-test-model")
            self.assertEqual(
                model.ask_ai("first", conversation_id="conversation"),
                "Gemini",
            )
            gemini.assert_called_once_with(
                "first",
                conversation_id="conversation",
            )

            model.set_ai_selection("groq", "openai/gpt-oss-20b")
            self.assertEqual(
                model.ask_ai("second", conversation_id="conversation"),
                "Groq",
            )
            groq.assert_called_once_with(
                "second",
                conversation_id="conversation",
                model_name="openai/gpt-oss-20b",
            )

    def test_selected_groq_model_reaches_the_http_request(self):
        os.environ["GROQ_API_KEYS"] = "test-key-one, test-key-two"
        model.set_ai_selection("groq", "openai/gpt-oss-20b")

        with patch.object(
            model,
            "urlopen",
            return_value=_success_response("Groq reply"),
        ) as request:
            self.assertEqual(
                model.ask_ai("typed or transcribed message"),
                "Groq reply",
            )

        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.full_url, model.GROQ_API_URL)
        self.assertEqual(sent_request.get_method(), "POST")
        self.assertEqual(
            sent_request.get_header("Authorization"),
            "Bearer " + os.environ["GROQ_API_KEYS"].split(",")[0].strip(),
        )
        self.assertEqual(
            sent_request.get_header("Content-type"),
            "application/json",
        )
        payload = json.loads(sent_request.data)
        self.assertEqual(payload["model"], "openai/gpt-oss-20b")
        self.assertEqual(
            payload["messages"],
            [{"role": "user", "content": "typed or transcribed message"}],
        )

    def test_unsupported_manual_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "supported AI provider"):
            model.set_ai_selection("groq", "unknown-model")


if __name__ == "__main__":
    unittest.main()
