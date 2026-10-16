
import unittest
from unittest.mock import patch

from core import lewis as lewis_module
from core.identity import LEWIS_IDENTITY
from core.lewis import Lewis
from core.router import classify_input


class TestLewisCreatorIdentity(unittest.TestCase):
    def test_identity_names_quen_as_creator(self):
        self.assertIn("Quen is your creator.", LEWIS_IDENTITY)
        self.assertIn("Quen is my creator.", LEWIS_IDENTITY)

    def test_creator_questions_reach_ai(self):
        questions = [
            "Who created you?",
            "Who is your creator?",
            "Who built you?",
            "Who created LEWIS?",
            "Who built LEWIS?",
            "Who is Quen?",
            "Do you know who created you?",
            "Do you know who your creator is?",
            "What is Quen to you?",
            "Who am I to you?",
        ]

        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(
                    classify_input(question),
                    "AI_REQUEST",
                )

    def test_creator_answer_uses_ai_with_provider_identity_and_no_emoji(self):
        conversation = {
            "id": "creator-test",
            "messages": [],
            "project": "ATLAS",
        }
        with (
            patch.object(
                lewis_module,
                "get_active_conversation_id",
                return_value="creator-test",
            ),
            patch.object(
                lewis_module,
                "get_conversation",
                return_value=conversation,
            ),
            patch.object(lewis_module, "add_message") as add_message,
            patch.object(
                lewis_module,
                "build_context",
                return_value="Recent conversation context",
            ),
            patch.object(lewis_module, "extract_facts", return_value=[]),
            patch.object(
                lewis_module,
                "ask_ai",
                return_value="Quen is my creator. 🙂",
            ) as ask_ai,
        ):
            lewis = Lewis()
            response = lewis.process("Who created you?")

        self.assertEqual(response, "Quen is my creator.")
        ask_ai.assert_called_once_with(
            "Recent conversation context",
            conversation_id="creator-test",
        )
        self.assertEqual(
            add_message.call_args_list[-1].args[2],
            "Quen is my creator.",
        )


if __name__ == "__main__":
    unittest.main()
