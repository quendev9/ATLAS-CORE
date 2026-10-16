import unittest
from unittest.mock import patch

from voice import speech_input


class FakeRecognizer:
    def AcceptWaveform(self, audio_data):
        return False

    def FinalResult(self):
        return '{"text":"recognized words"}'


class FakeInputStream:
    active = False

    def __init__(self, **options):
        pass

    def __enter__(self):
        FakeInputStream.active = True
        return self

    def __exit__(self, *args):
        FakeInputStream.active = False


class SpeechInputTests(unittest.TestCase):
    def test_capture_callback_and_timings_do_not_log_transcript(self):
        capture_state = []
        events = []

        def mark_capturing():
            capture_state.append(FakeInputStream.active)

        with (
            patch.object(speech_input, "_get_model", return_value=object()),
            patch.object(
                speech_input,
                "KaldiRecognizer",
                return_value=FakeRecognizer(),
            ),
            patch.object(speech_input.sd, "RawInputStream", FakeInputStream),
            patch.object(speech_input, "log_event", side_effect=events.append),
        ):
            transcript = speech_input.listen_once(
                timeout=0,
                on_capture_start=mark_capturing,
            )

        self.assertEqual(transcript, "recognized words")
        self.assertEqual(capture_state, [True])
        self.assertEqual(len(events), 2)
        self.assertIn("VOICE INPUT CAPTURE:", events[0])
        self.assertIn("VOICE TRANSCRIPTION:", events[1])
        self.assertNotIn("recognized words", " ".join(events))


if __name__ == "__main__":
    unittest.main()
