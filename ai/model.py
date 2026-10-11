import threading
import os

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError


load_dotenv()

TRANSIENT_API_STATUS_CODES = {408, 429}

_client = None
_chat = None
_conversation_chats = {}
_client_lock = threading.Lock()
_request_lock = threading.Lock()


def _get_chat(conversation_id=None):
    global _client, _chat

    with _client_lock:
        if conversation_id is None:
            cached_chat = _chat
        else:
            cached_chat = _conversation_chats.get(conversation_id)
        if cached_chat is not None:
            return cached_chat

        if _client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY was not found in the .env file"
                )

            client = genai.Client(api_key=api_key)
            try:
                chat = client.chats.create(model="gemini-3.6-flash")
            except Exception:
                client.close()
                raise

            _client = client
        else:
            chat = _client.chats.create(model="gemini-3.6-flash")

        if conversation_id is None:
            _chat = chat
        else:
            _conversation_chats[conversation_id] = chat
        return chat


def ask_gemini(message, conversation_id=None):
    with _request_lock:
        try:
            response = _get_chat(conversation_id).send_message(message)
        except RuntimeError as error:
            error_message = str(error).casefold()
            if "client" in error_message and "closed" in error_message:
                _discard_closed_client()
            raise

        return response.text


def _discard_closed_client():
    """Discard an SDK client that reports it is already closed."""
    global _client, _chat

    with _client_lock:
        _client = None
        _chat = None
        _conversation_chats.clear()


def close_gemini():
    """Close the shared Gemini client once and discard its chat session."""
    global _client, _chat

    with _request_lock:
        with _client_lock:
            client = _client
            _client = None
            _chat = None
            _conversation_chats.clear()

            if client is not None:
                client.close()


def is_transient_api_error(error):
    """Return whether a Gemini API error is likely to resolve on retry."""
    if not isinstance(error, APIError):
        return False

    status_code = getattr(error, "code", None)

    return (
        isinstance(status_code, int)
        and not isinstance(status_code, bool)
        and (
            status_code in TRANSIENT_API_STATUS_CODES
            or 500 <= status_code <= 599
        )
    )