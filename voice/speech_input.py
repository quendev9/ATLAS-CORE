
import json
import queue
import time
from pathlib import Path

import sounddevice as sd
from vosk import Model, KaldiRecognizer


MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "vosk-model-small-en-us-0.15"
)

SAMPLE_RATE = 16000
BLOCK_SIZE = 4000
LISTEN_TIMEOUT = 15


_model = None


def _get_model():
    global _model

    if _model is None:
        if not MODEL_PATH.is_dir():
            raise FileNotFoundError(
                f"Vosk model folder not found: {MODEL_PATH}"
            )

        _model = Model(str(MODEL_PATH))

    return _model


def listen_once(timeout=LISTEN_TIMEOUT):
    """Listen through the default microphone and return recognized text."""
    audio_queue = queue.Queue()
    recognizer = KaldiRecognizer(_get_model(), SAMPLE_RATE)

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(f"\nMicrophone status: {status}")

        audio_queue.put(bytes(indata))

    print("Listening... Speak now.")

    deadline = time.monotonic() + timeout

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while time.monotonic() < deadline:
            try:
                audio_data = audio_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            if recognizer.AcceptWaveform(audio_data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()

                if text:
                    return text

        result = json.loads(recognizer.FinalResult())
        return result.get("text", "").strip()
