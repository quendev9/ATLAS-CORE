import unittest
from unittest.mock import Mock, patch

from voice import speech_output


class SpeechOutputTests(unittest.TestCase):
    def test_prepare_speech_removes_markdown_without_losing_content(self):
        markdown = (
            "# Release notes\n\n"
            "**Bold** and *italic* text, plus ~~removed~~ text.\n"
            "[Documentation](https://example.com/guide?q=42)\n"
            "- First item\n"
            "2. Second item with 12 steps.\n"
            "> Quoted text.\n"
            "`openai/gpt-oss-120b`\n"
            "```python\nprint('value 42')\n```"
        )

        spoken = speech_output._prepare_speech(markdown)

        self.assertIn("Release notes", spoken)
        self.assertIn("Bold and italic text", spoken)
        self.assertIn("removed text", spoken)
        self.assertIn(
            "Documentation (https://example.com/guide?q=42)",
            spoken,
        )
        self.assertIn("First item", spoken)
        self.assertIn("2. Second item with 12 steps.", spoken)
        self.assertIn("Quoted text.", spoken)
        self.assertIn("openai/gpt-oss-120b", spoken)
        self.assertIn("print('value 42')", spoken)
        self.assertNotIn("#", spoken)
        self.assertNotIn("**", spoken)
        self.assertNotIn("```", spoken)
        self.assertNotIn("`", spoken)

    def test_speak_uses_clean_text_and_reports_playback_start(self):
        playback_started = Mock()

        def play(text, cancel_event=None, on_playback_start=None):
            self.assertEqual(text, "A bold response.")
            on_playback_start()

        with patch.object(speech_output, "_speak_fish", side_effect=play):
            self.assertTrue(speech_output.speak(
                "**A bold response.**",
                on_playback_start=playback_started,
            ))

        playback_started.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
