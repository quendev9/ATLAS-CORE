
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from google.genai.errors import ServerError

from ai import model
import main as atlas_main
import memory.conversations as conversations
from core.atlas import Atlas
from core.context_builder import build_context
from memory import memory as personal_memory
from memory import project_memory
from memory.manager import get_memories, remember_memory


class ConversationIntegrityTests(unittest.TestCase):

    def setUp(self):
        self.provider_patch = patch.dict(
            os.environ,
            {"AI_PROVIDER": "gemini"},
        )
        self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.conversations_file = (
            Path(self.temp_dir.name) / "conversations.json"
        )

        self.file_patch = patch.object(
            conversations,
            "CONVERSATIONS_FILE",
            self.conversations_file,
        )
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)

        self.personal_memory_patch = patch.object(
            personal_memory,
            "MEMORY_FILE",
            Path(self.temp_dir.name) / "memory.json",
        )
        self.personal_memory_patch.start()
        self.addCleanup(self.personal_memory_patch.stop)

        self.project_memory_patch = patch.object(
            project_memory,
            "PROJECT_MEMORY_FILE",
            Path(self.temp_dir.name) / "project_memory.json",
        )
        self.project_memory_patch.start()
        self.addCleanup(self.project_memory_patch.stop)

        self.addCleanup(self.temp_dir.cleanup)

    def test_new_conversation_command_stays_in_original_conversation(self):
        atlas = Atlas()
        original_id = atlas.active_conversation_id

        response = atlas.process(
            "start a new conversation Robotics Lab"
        )

        original = conversations.get_conversation(original_id)
        active_id = conversations.get_active_conversation_id()
        active = conversations.get_conversation(active_id)

        self.assertIsNotNone(original)
        self.assertEqual(
            [message["role"] for message in original["messages"]],
            ["user", "assistant"],
        )
        self.assertEqual(
            original["messages"][0]["content"],
            "start a new conversation Robotics Lab",
        )
        self.assertEqual(
            original["messages"][1]["content"],
            response,
        )

        self.assertNotEqual(active_id, original_id)
        self.assertEqual(active["title"], "Robotics Lab")
        self.assertEqual(atlas.active_conversation_id, active_id)

    def test_switch_command_persists_selection_and_saves_exchange(self):
        atlas = Atlas()
        original_id = atlas.active_conversation_id

        target = conversations.create_conversation(
            title="Robotics Lab",
            project="ATLAS",
        )

        # Restore the original conversation before issuing the command.
        conversations.set_active_conversation(original_id)
        atlas.active_conversation_id = original_id

        response = atlas.process("switch to Robotics Lab")

        original = conversations.get_conversation(original_id)

        self.assertEqual(
            conversations.get_active_conversation_id(),
            target["id"],
        )
        self.assertEqual(
            atlas.active_conversation_id,
            target["id"],
        )
        self.assertEqual(
            [message["role"] for message in original["messages"]],
            ["user", "assistant"],
        )
        self.assertEqual(
            original["messages"][1]["content"],
            response,
        )

    def test_ai_failure_is_recorded_and_returns_a_controlled_fallback(self):
        atlas = Atlas()
        conversation_id = atlas.active_conversation_id

        with patch(
            "core.atlas.ask_ai",
            side_effect=RuntimeError("simulated failure"),
        ):
            response = atlas.process("Explain my robotics project")

        conversation = conversations.get_conversation(conversation_id)
        roles = [
            message["role"]
            for message in conversation["messages"]
        ]

        self.assertEqual(roles, ["user", "error", "assistant"])
        self.assertIn(
            "RuntimeError",
            conversation["messages"][-2]["content"],
        )
        self.assertEqual(
            response,
            Atlas.MODEL_UNAVAILABLE_RESPONSE,
        )
        self.assertEqual(
            conversation["messages"][-1]["content"],
            Atlas.MODEL_UNAVAILABLE_RESPONSE,
        )

    def test_gemini_429_explains_quota_and_records_provider_detail(self):
        atlas = Atlas()
        conversation_id = atlas.active_conversation_id
        rate_limit_error = ServerError(
            429,
            {
                "error": {
                    "message": "Quota exceeded for this project.",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
        )

        with patch(
            "core.atlas.ask_ai",
            side_effect=rate_limit_error,
        ):
            response = atlas.process("Explain my robotics project")

        conversation = conversations.get_conversation(conversation_id)
        error_message = conversation["messages"][-2]["content"]

        self.assertEqual(response, Atlas.MODEL_RATE_LIMIT_RESPONSE)
        self.assertIn("quota", response.lower())
        self.assertIn("429", error_message)
        self.assertIn("Quota exceeded", error_message)
        self.assertEqual(
            conversation["messages"][-1]["content"],
            Atlas.MODEL_RATE_LIMIT_RESPONSE,
        )

    def test_groq_provider_uses_selected_backend(self):
        atlas = Atlas()

        with (
            patch.object(model, "_selected_ai_model", None),
            patch.dict(
                os.environ,
                {
                    "AI_PROVIDER": "groq",
                    "GROQ_MODEL": "openai/gpt-oss-20b",
                },
            ),
            patch(
                "ai.model.ask_groq",
                return_value="Groq reply",
            ) as ask_groq,
        ):
            model.set_ai_selection("groq", "openai/gpt-oss-20b")
            response = atlas.process("Tell me a story")

        self.assertEqual(response, "Groq reply")
        ask_groq.assert_called_once()

    def test_groq_http_statuses_have_provider_specific_fallbacks(self):
        error_cases = (
            (401, Atlas.MODEL_AUTHENTICATION_RESPONSE),
            (403, Atlas.MODEL_PERMISSION_RESPONSE),
            (404, Atlas.MODEL_NOT_FOUND_RESPONSE),
            (429, Atlas.MODEL_RATE_LIMIT_RESPONSE),
            (503, Atlas.MODEL_SERVER_ERROR_RESPONSE),
        )

        for status_code, expected_template in error_cases:
            with self.subTest(status_code=status_code):
                atlas = Atlas()
                with (
                    patch.object(model, "_selected_ai_model", None),
                    patch.dict(
                        os.environ,
                        {
                            "AI_PROVIDER": "groq",
                            "GROQ_MODEL": "openai/gpt-oss-20b",
                        },
                    ),
                    patch(
                        "ai.model.ask_groq",
                        side_effect=model.GroqAPIError(
                            status_code,
                            "provider diagnostic detail",
                        ),
                    ),
                ):
                    model.set_ai_selection(
                        "groq",
                        "openai/gpt-oss-20b",
                    )
                    response = atlas.process(
                        f"Test provider status {status_code}"
                    )

                self.assertEqual(
                    response,
                    expected_template.replace("Gemini", "Groq"),
                )
                error_message = conversations.get_conversation(
                    atlas.active_conversation_id
                )["messages"][-2]["content"]
                self.assertIn("provider diagnostic detail", error_message)

    def test_corrupt_conversation_file_is_preserved(self):
        corrupted = '{"conversations": ['
        self.conversations_file.write_text(corrupted, encoding="utf-8")

        with self.assertRaises(json.JSONDecodeError):
            conversations.load_conversations()

        self.assertEqual(
            self.conversations_file.read_text(encoding="utf-8"),
            corrupted,
        )

    def test_failed_conversation_write_keeps_previous_file(self):
        conversations.save_conversations(
            {"conversations": [], "active_conversation_id": None}
        )
        original = self.conversations_file.read_bytes()

        with patch(
            "memory.conversations.os.replace",
            side_effect=OSError("disk unavailable"),
        ):
            with self.assertRaises(OSError):
                conversations.save_conversations(
                    {
                        "conversations": [{"id": "new"}],
                        "active_conversation_id": "new",
                    }
                )

        self.assertEqual(self.conversations_file.read_bytes(), original)
        self.assertEqual(
            list(self.conversations_file.parent.glob(".conversations.json.*.tmp")),
            [],
        )

    def test_gemini_503_does_not_stop_interactive_loop(self):
        atlas = Atlas()
        unavailable = ServerError(503, {"error": "temporarily unavailable"})

        with (
            patch("main.Atlas", return_value=atlas),
            patch(
                "builtins.input",
                side_effect=[
                    "1",
                    "Explain my robotics project",
                    "Tell me a story",
                    "exit",
                ],
            ),
            patch("builtins.print") as printed,
            patch(
                "core.atlas.ask_ai",
                side_effect=[unavailable, "Gemini is back."],
            ) as ask_gemini,
        ):
            atlas_main.main()

        self.assertEqual(
            ask_gemini.call_args.kwargs["conversation_id"],
            atlas.active_conversation_id,
        )
        self.assertEqual(ask_gemini.call_count, 2)
        self.assertEqual(atlas.state, "ready")
        printed.assert_any_call(
            f"ATLAS: {Atlas.MODEL_SERVER_ERROR_RESPONSE}"
        )
        printed.assert_any_call("ATLAS: Gemini is back.")

        conversation = conversations.get_conversation(
            atlas.active_conversation_id
        )
        self.assertEqual(
            [message["role"] for message in conversation["messages"]],
            ["user", "error", "assistant", "user", "assistant"],
        )

    def test_closed_client_failure_keeps_memory_and_console_loop_usable(self):
        atlas = Atlas()
        closed_client_error = RuntimeError(
            "Cannot send a request, as the client has been closed."
        )

        with (
            patch("main.Atlas", return_value=atlas),
            patch(
                "builtins.input",
                side_effect=[
                    "1",
                    "my test robot's name is copperhead",
                    "Tell me a story",
                    "exit",
                ],
            ),
            patch("builtins.print") as printed,
            patch(
                "core.atlas.ask_ai",
                side_effect=[closed_client_error, "Gemini recovered."],
            ) as ask_gemini,
            patch("main.close_gemini") as close_gemini,
        ):
            atlas_main.main()

        self.assertEqual(ask_gemini.call_count, 2)
        close_gemini.assert_called_once_with()
        printed.assert_any_call(
            "ATLAS: I'm having trouble reaching Gemini right now. "
            "Please try again in a moment."
        )
        printed.assert_any_call("ATLAS: Gemini recovered.")

        facts = project_memory.get_project_facts("ATLAS")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["subject"], "test robot")
        self.assertEqual(facts[0]["value"], "copperhead")
        self.assertEqual(atlas.state, "ready")

    def test_assistant_suggestions_remain_conversation_only(self):
        atlas = Atlas()
        with patch(
            "core.atlas.ask_ai",
            return_value="You could use a Raspberry Pi for the cyberdeck.",
        ):
            atlas.process("Can you suggest hardware for my cyberdeck?")

        self.assertEqual(get_memories(), [])
        self.assertEqual(
            project_memory.get_project_facts(),
            [],
        )
        conversation = conversations.get_conversation(
            atlas.active_conversation_id
        )
        self.assertIn(
            "You could use a Raspberry Pi",
            conversation["messages"][-1]["content"],
        )

    def test_context_reads_only_the_requested_conversation_history(self):
        first = conversations.create_conversation("First", project="ATLAS")
        first_id = first["id"]
        conversations.add_message(
            first_id,
            "user",
            "I am building DUM-E.",
        )
        second = conversations.create_conversation("Second", project="ATLAS")
        conversations.add_message(
            second["id"],
            "user",
            "I chose an unrelated project component.",
        )

        context = build_context(
            first_id,
            "What am I building?",
            project_name="ATLAS",
            max_memory_facts=0,
        )

        self.assertIn("I am building DUM-E.", context)
        self.assertNotIn("unrelated project component", context)

    def test_conversations_share_long_term_memory_not_each_others_history(self):
        remember_memory("favorite color", "blue", "preference")
        first = conversations.create_conversation("First", project="ATLAS")
        conversations.add_message(
            first["id"],
            "user",
            "Private first-conversation detail.",
        )
        second = conversations.create_conversation("Second", project="ATLAS")
        conversations.add_message(
            second["id"],
            "user",
            "Second-conversation detail.",
        )

        context = build_context(
            second["id"],
            "What is my favorite color?",
            project_name="ATLAS",
        )

        self.assertIn("blue", context)
        self.assertIn("Second-conversation detail.", context)
        self.assertNotIn("Private first-conversation detail.", context)

    def test_user_correction_updates_project_decision_history(self):
        atlas = Atlas()
        with patch(
            "core.atlas.ask_ai",
            return_value="Understood.",
        ):
            atlas.process(
                "I chose a Raspberry Pi as a hardware component "
                "for my cyberdeck."
            )
            atlas.process(
                "Actually, I chose an Arduino as a hardware component "
                "for my cyberdeck."
            )

        facts = project_memory.get_project_facts("ATLAS")
        decision = next(
            fact
            for fact in facts
            if fact["subject"] == "cyberdeck"
            and fact["predicate"] == "chosen_component"
        )
        self.assertEqual(decision["value"], "an Arduino")
        self.assertEqual(decision["history"][0]["value"], "a Raspberry Pi")


if __name__ == "__main__":
    unittest.main()