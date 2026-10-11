
import html
import re

import pyttsx3


_engine = None


def _get_engine():
    global _engine

    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 175)
        _engine.setProperty("volume", 1.0)

    return _engine


def prepare_speech(text):
    """Convert a Markdown-heavy response into cleaner spoken text."""
    if not isinstance(text, str) or not text.strip():
        return ""

    text = html.unescape(text)

    # Replace code blocks instead of reading programming syntax aloud.
    text = re.sub(
        r"```.*?```",
        "I've included a code example in the text response.",
        text,
        flags=re.DOTALL,
    )

    # Keep link labels but remove raw URLs.
    text = re.sub(r"!?\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "the linked page", text)

    # Remove common Markdown formatting.
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)

    # Make lists and spacing sound more natural.
    text = re.sub(r"(?m)^\s*[-+]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def speak(text):
    """Speak a cleaned response using the local system voice."""
    spoken_text = prepare_speech(text)

    if not spoken_text:
        return

    engine = _get_engine()
    engine.say(spoken_text)
    engine.runAndWait()


def stop_speaking():
    """Stop queued speech if the engine has been initialized."""
    if _engine is not None:
        _engine.stop()
