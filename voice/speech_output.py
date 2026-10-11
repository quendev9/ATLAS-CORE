
import os
import re
import tempfile
import threading
from pathlib import Path

import pyttsx3
from dotenv import load_dotenv
from fishaudio import FishAudio
from fishaudio.utils import save


load_dotenv()

VOICE_ID = "e13fa398a7f445a685316a3de6089ce7"
FISH_MODEL = "s2.1-pro-free"

_engine = None
_fish_client = None
_speech_lock = threading.Lock()
_stop_requested = threading.Event()


def _get_engine():
    """Initialize the local fallback voice when needed."""
    global _engine

    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 175)
        _engine.setProperty("volume", 1.0)

    return _engine


def _get_fish_client():
    """Create the Fish Audio client using the key stored in .env."""
    global _fish_client

    if _fish_client is None:
        api_key = os.getenv("FISH_API_KEY")

        if not api_key:
            raise RuntimeError("FISH_API_KEY is missing from .env")

        _fish_client = FishAudio(api_key=api_key)

    return _fish_client


def _prepare_speech(text):
    """Remove common Markdown formatting before speaking."""
    text = re.sub(r"```.*?```", " Code block omitted. ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(?<!\w)[*_](.*?)[*_](?!\w)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _speak_fish(text):
    """Generate and play speech using Fish Audio."""
    client = _get_fish_client()

    audio = client.tts.convert(
        text=text,
        reference_id=VOICE_ID,
        model=FISH_MODEL,
        format="mp3",
    )

    # Save to a temporary file rather than leaving audio files in the repo.
    with tempfile.NamedTemporaryFile(
        suffix=".mp3", delete=False
    ) as audio_file:
        audio_path = Path(audio_file.name)

    try:
        save(audio, str(audio_path))

        if _stop_requested.is_set():
            return

        # Plays through the system's default audio player.
        # Install playsound if this import is unavailable.
        from playsound import playsound

        if not _stop_requested.is_set():
            playsound(str(audio_path))
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except OSError:
            pass


def _speak_local(text):
    """Speak with the existing offline Windows/system voice."""
    engine = _get_engine()
    engine.say(text)
    engine.runAndWait()


def speak(text):
    """Speak with Fish Audio, falling back to the local voice on errors."""
    if not isinstance(text, str) or not text.strip():
        return

    clean_text = _prepare_speech(text)
    if not clean_text:
        return

    with _speech_lock:
        _stop_requested.clear()

        try:
            _speak_fish(clean_text)
        except Exception as error:
            print(f"[ATLAS voice] Fish Audio unavailable: {error}")
            print("[ATLAS voice] Using local fallback voice.")

            try:
                if not _stop_requested.is_set():
                    _speak_local(clean_text)
            except Exception as fallback_error:
                print(f"[ATLAS voice] Local speech failed: {fallback_error}")


def stop_speaking():
    """Request speech to stop and stop the local engine if initialized."""
    _stop_requested.set()

    if _engine is not None:
        try:
            _engine.stop()
        except Exception:
            pass
