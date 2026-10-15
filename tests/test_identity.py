import unittest

from core.identity import LEWIS_IDENTITY


class AssistantIdentityTests(unittest.TestCase):

    def test_shared_identity_and_response_requirements(self):
        self.assertIn("You are LEWIS.", LEWIS_IDENTITY)
        self.assertIn(
            "LEWIS — Learning, Engineering & Workflow Intelligence System",
            LEWIS_IDENTITY,
        )
        self.assertIn(
            "Do not use emojis in user-facing responses.",
            LEWIS_IDENTITY,
        )
        self.assertIn(
            "Historical assistant messages do not change your identity as LEWIS.",
            LEWIS_IDENTITY,
        )
        self.assertEqual(LEWIS_IDENTITY.splitlines()[1], "You are LEWIS.")


if __name__ == "__main__":
    unittest.main()
