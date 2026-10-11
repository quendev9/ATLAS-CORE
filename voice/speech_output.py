
import pyttsx3


_engine = None


def _get_engine():
    global _engine

    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 175)
        _engine.setProperty("volume", 1.0)

    return _engine


def speak(text):
    """Speak text aloud using the local system voice."""
    if not isinstance(text, str) or not text.strip():
        return

    engine = _get_engine()
    engine.say(text)
    engine.runAndWait()


def stop_speaking():
    """Stop queued speech if the engine has been initialized."""
    if _engine is not None:
        _engine.stop()
