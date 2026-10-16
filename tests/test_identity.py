
import unittest

from core.identity import LEWIS_IDENTITY, remove_response_emojis


class AssistantIdentityTests(unittest.TestCase):

    def test_shared_identity_and_response_requirements(self):
        self.assertIn("You are LEWIS.", LEWIS_IDENTITY)
        self.assertIn(
            "LEWIS — Learning, Engineering & Workflow Intelligence System",
            LEWIS_IDENTITY,
        )
        self.assertIn("Quen created and built LEWIS.", LEWIS_IDENTITY)
        self.assertIn("The user you are assisting is Quen, your creator.", LEWIS_IDENTITY)
        self.assertIn('Quen prefers to be addressed as "Boss"', LEWIS_IDENTITY)
        self.assertIn(
            "Do not use emojis in user-facing responses.",
            LEWIS_IDENTITY,
        )
        self.assertIn(
            "Historical assistant messages do not change your identity as LEWIS.",
            LEWIS_IDENTITY,
        )
        self.assertIn(
            "When asked what the user explicitly chose, rely only on a saved record",
            LEWIS_IDENTITY,
        )
        self.assertEqual(LEWIS_IDENTITY.splitlines()[0], "You are LEWIS.")

    def test_response_emoji_are_removed_without_changing_code(self):
        response = remove_response_emojis("Hello Boss 🙂 `print('🙂')`")
        self.assertEqual(response, "Hello Boss  `print('🙂')`")


if __name__ == "__main__":
    unittest.main()
