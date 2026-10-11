
import unittest
from unittest.mock import patch

from core.context_builder import build_context


class ContextBuilderTests(unittest.TestCase):

    def setUp(self):
        self.conversation = {
            "messages": [
                {
                    "id": "msg-1",
                    "role": "user",
                    "content": "I am building ATLAS, my autonomous assistant.",
                },
                {
                    "id": "msg-2",
                    "role": "assistant",
                    "content": "ATLAS can use memory and tools.",
                },
                {
                    "id": "msg-3",
                    "role": "user",
                    "content": "I am also learning robotics with Arduino.",
                },
                {
                    "id": "msg-4",
                    "role": "user",
                    "content": "What do you remember about robotics?",
                },
            ],
            "summary": None,
            "summary_coverage": {},
            "project": "ATLAS",
        }

        self.personal_memories = [
            {
                "subject": "user",
                "predicate": "interests",
                "key": "interests",
                "value": "robotics and Arduino",
                "category": "interest",
            },
            {
                "subject": "user",
                "predicate": "favorite color",
                "key": "favorite color",
                "value": "blue",
                "category": "preference",
            },
        ]

        self.project_facts = [
            {
                "subject": "ATLAS",
                "predicate": "uses",
                "value": "persistent memory and reasoning",
                "category": "architecture",
                "status": "plan",
            },
            {
                "subject": "ATLAS",
                "predicate": "interface_color",
                "value": "dark green",
                "category": "design",
            },
        ]

    def _build(self, **kwargs):
        with (
            patch(
                "core.context_builder.get_conversation",
                return_value=self.conversation,
            ),
            patch(
                "core.context_builder.get_memories",
                return_value=self.personal_memories,
            ),
            patch(
                "core.context_builder.get_project_facts",
                return_value=self.project_facts,
            ),
        ):
            return build_context(
                conversation_id="conversation-1",
                user_message="What do you remember about robotics?",
                project_name="ATLAS",
                **kwargs,
            )

    def test_relevant_personal_memory_is_included(self):
        context = self._build()

        self.assertIn("robotics and Arduino", context)
        self.assertIn("[status: stated]", context)

    def test_unrelated_memory_is_not_selected_when_limit_is_one(self):
        context = self._build(max_memory_facts=1)

        self.assertIn("robotics and Arduino", context)
        self.assertNotIn("favorite color", context)

    def test_relevant_older_message_is_retrieved(self):
        context = self._build(max_recent_messages=1)

        self.assertIn(
            "I am also learning robotics with Arduino.",
            context,
        )

    def test_context_never_exceeds_character_limit(self):
        context = self._build(max_chars=180)

        self.assertLessEqual(len(context), 180)

    def test_zero_character_limit_returns_empty_string(self):
        context = self._build(max_chars=0)

        self.assertEqual(context, "")

    def test_zero_recent_messages_does_not_include_recent_history(self):
        context = self._build(max_recent_messages=0)

        self.assertNotIn("Recent conversation:", context)

    def test_missing_conversation_returns_fallback(self):
        with (
            patch(
                "core.context_builder.get_conversation",
                return_value=None,
            ),
            patch(
                "core.context_builder.get_memories",
                return_value=[],
            ),
            patch(
                "core.context_builder.get_project_facts",
                return_value=[],
            ),
        ):
            context = build_context(
                conversation_id="missing",
                user_message="Unrelated question",
            )

        self.assertEqual(context, "No prior context available.")

    def test_negative_limits_raise_value_error(self):
        with self.assertRaises(ValueError):
            self._build(max_chars=-1)


if __name__ == "__main__":
    unittest.main()