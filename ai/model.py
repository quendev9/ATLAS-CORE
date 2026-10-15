
import json
import os
import re
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError


load_dotenv()

TRANSIENT_API_STATUS_CODES = {408, 429}
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

_client = None
_chat = None
_conversation_chats = {}
_client_lock = threading.Lock()
_request_lock = threading.Lock()
_groq_key_lock = threading.Lock()
_selection_lock = threading.Lock()
_groq_next_key_index = 0
_selected_ai_model = None


def _configured_gemini_model():
    return os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


def _configured_groq_model():
    return os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def _configured_openrouter_model():
    return os.getenv("OPENROUTER_MODEL", "openrouter/free")


def get_available_ai_models():
    """Return the provider/model choices that ATLAS can currently select."""
    return [
        {
            "provider": "gemini",
            "name": "Gemini",
            "model": _configured_gemini_model(),
        },
        {
            "provider": "groq",
            "name": "Groq",
            "model": _configured_groq_model(),
        },
        {
            "provider": "openrouter",
            "name": "OpenRouter",
            "model": _configured_openrouter_model(),
        },
    ]


def _environment_ai_selection():
    provider = (
        os.getenv("AI_PROVIDER", "gemini").strip().casefold() or "gemini"
    )
    models = get_available_ai_models()
    selected = next(
        (item for item in models if item["provider"] == provider),
        models[0],
    )
    return selected["provider"], selected["model"]


def get_ai_selection():
    """Return the runtime selection, or the environment-configured default."""
    with _selection_lock:
        selection = _selected_ai_model

    provider, model_name = selection or _environment_ai_selection()
    return {"provider": provider, "model": model_name}


def set_ai_selection(provider, model_name):
    """Set the process-local provider/model selection after validation."""
    if not isinstance(provider, str) or not isinstance(model_name, str):
        raise ValueError("Choose a supported AI provider and model.")

    available = get_available_ai_models()
    if not any(
        item["provider"] == provider and item["model"] == model_name
        for item in available
    ):
        raise ValueError("Choose a supported AI provider and model.")

    global _selected_ai_model
    with _selection_lock:
        _selected_ai_model = (provider, model_name)

    return get_ai_selection()


def get_ai_provider():
    """Return the provider for the current runtime selection."""
    return get_ai_selection()["provider"]


def get_ai_provider_info():
    """Return the selected provider's display name, model, and key status."""
    selection = get_ai_selection()
    provider = selection["provider"]
    display_names = {
        "gemini": "Gemini",
        "groq": "Groq",
        "openrouter": "OpenRouter",
    }

    if provider == "gemini":
        configured = bool(os.getenv("GEMINI_API_KEY", "").strip())
    elif provider == "groq":
        configured = bool(_get_groq_api_keys())
    elif provider == "openrouter":
        configured = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
    else:
        configured = False

    return {
        "provider": display_names.get(provider, provider),
        "model": selection["model"],
        "configured": configured,
        "selection": selection,
    }


def _get_groq_api_keys():
    configured_keys = [
        os.getenv("GROQ_API_KEYS", ""),
        os.getenv("GROQ_API_KEY", ""),
    ]
    keys = []

    for configured_value in configured_keys:
        keys.extend(
            key.strip()
            for key in re.split(r"[, \r\n]+", configured_value)
            if key.strip()
        )

    return list(dict.fromkeys(keys))


def _next_groq_key_index(key_count):
    global _groq_next_key_index

    with _groq_key_lock:
        index = _groq_next_key_index % key_count
        _groq_next_key_index = (index + 1) % key_count
        return index


class GroqAPIError(RuntimeError):
    """An HTTP error returned by the Groq API."""

    def __init__(self, status_code, message):
        safe_message = str(message)
        for api_key in _get_groq_api_keys():
            safe_message = safe_message.replace(api_key, "[REDACTED]")

        super().__init__(safe_message)
        self.code = status_code
        self.status_code = status_code


def _provider_error_message(error, provider_name):
    response_body = error.read()

    try:
        payload = json.loads(response_body.decode("utf-8"))
    except (UnicodeError, ValueError):
        detail = response_body.decode("utf-8", errors="replace").strip()
        if detail:
            return detail[:500]
        return f"{provider_name} API request failed with HTTP {error.code}."

    if isinstance(payload, dict):
        detail = payload.get("error")

        if isinstance(detail, dict):
            message = detail.get("message")
            additional_details = [
                f"{name}={detail[name]}"
                for name in ("code", "type")
                if isinstance(detail.get(name), (str, int))
                and str(detail[name]).strip()
            ]

            if isinstance(message, str) and message.strip():
                suffix = (
                    f" ({', '.join(additional_details)})"
                    if additional_details
                    else ""
                )
                return f"{message.strip()}{suffix}"[:500]

            if additional_details:
                return ", ".join(additional_details)[:500]

        if isinstance(detail, str) and detail.strip():
            return detail.strip()[:500]

    return json.dumps(payload, ensure_ascii=False)[:500]


def _groq_error_message(error):
    return _provider_error_message(error, "Groq")


def ask_groq(message, conversation_id=None, model_name=None):
    """Send a prompt to Groq, rotating keys for retryable key-specific errors."""
    del conversation_id  # Conversation context is already in the prompt.

    with _request_lock:
        api_keys = _get_groq_api_keys()
        if not api_keys:
            raise RuntimeError(
                "GROQ_API_KEYS or GROQ_API_KEY was not found in the .env file"
            )

        model_name = model_name or _configured_groq_model()
        request_body = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": message}],
        }).encode("utf-8")

        first_key_index = _next_groq_key_index(len(api_keys))
        last_error = None

        for offset in range(len(api_keys)):
            api_key = api_keys[(first_key_index + offset) % len(api_keys)]

            request = Request(
                GROQ_API_URL,
                data=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "ATLAS-Core/1.0",
                },
                method="POST",
            )

            try:
                with urlopen(request, timeout=60) as response:
                    payload = json.loads(response.read().decode("utf-8"))

            except HTTPError as error:
                last_error = GroqAPIError(
                    error.code,
                    _groq_error_message(error),
                )

                # A 403 can be an edge-protection block. Retrying other keys
                # won't fix that, so surface the error immediately.
                if error.code == 403:
                    raise last_error from error

                # Retry another key for authentication failures or rate limits.
                if error.code not in (401, 429):
                    raise last_error from error

                continue

            try:
                content = payload["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as error:
                raise RuntimeError(
                    "Groq returned a response without message content."
                ) from error

            if not isinstance(content, str):
                raise RuntimeError(
                    "Groq returned message content in an unsupported format."
                )

            return content

        if last_error is not None:
            raise last_error

        raise RuntimeError("Groq request failed without a provider error.")


class OpenRouterAPIError(RuntimeError):
    """An HTTP error returned by the OpenRouter API."""

    def __init__(self, status_code, message):
        safe_message = str(message)
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

        if api_key:
            safe_message = safe_message.replace(api_key, "[REDACTED]")

        super().__init__(safe_message)
        self.code = status_code
        self.status_code = status_code


def ask_openrouter(message, conversation_id=None, model_name=None):
    """Send a prompt to OpenRouter using the configured API key."""
    del conversation_id  # Conversation context is already in the prompt.

    with _request_lock:
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY was not found in the .env file"
            )

        request_body = json.dumps({
            "model": model_name or _configured_openrouter_model(),
            "messages": [{"role": "user", "content": message}],
        }).encode("utf-8")

        request = Request(
            OPENROUTER_API_URL,
            data=request_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise OpenRouterAPIError(
                error.code,
                _provider_error_message(error, "OpenRouter"),
            ) from error

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(
                "OpenRouter returned a response without message content."
            ) from error

        if not isinstance(content, str):
            raise RuntimeError(
                "OpenRouter returned message content in an unsupported format."
            )

        return content


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
                chat = client.chats.create(
                    model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
                )
            except Exception:
                client.close()
                raise

            _client = client
        else:
            chat = _client.chats.create(
                model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
            )

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


def _ask_gemini_selected(message, conversation_id, model_name):
    if model_name != _configured_gemini_model():
        raise ValueError("The selected Gemini model is no longer configured.")

    return ask_gemini(message, conversation_id=conversation_id)


def _ask_groq_selected(message, conversation_id, model_name):
    return ask_groq(
        message,
        conversation_id=conversation_id,
        model_name=model_name,
    )


def _ask_openrouter_selected(message, conversation_id, model_name):
    return ask_openrouter(
        message,
        conversation_id=conversation_id,
        model_name=model_name,
    )


_AI_PROVIDER_ADAPTERS = {
    "gemini": _ask_gemini_selected,
    "groq": _ask_groq_selected,
    "openrouter": _ask_openrouter_selected,
}


def ask_ai(message, conversation_id=None):
    """Dispatch a prompt through the selected provider adapter."""
    selection = get_ai_selection()
    adapter = _AI_PROVIDER_ADAPTERS.get(selection["provider"])

    if adapter is None:
        raise ValueError(
            f"Unsupported AI provider: {selection['provider']}"
        )

    return adapter(
        message,
        conversation_id,
        selection["model"],
    )


def is_transient_api_error(error):
    """Return whether a provider API error is likely to resolve on retry."""
    if isinstance(error, APIError):
        status_code = getattr(error, "code", None)
    elif isinstance(error, GroqAPIError):
        status_code = error.status_code
    elif isinstance(error, OpenRouterAPIError):
        status_code = error.status_code
    else:
        return False

    return (
        isinstance(status_code, int)
        and not isinstance(status_code, bool)
        and (
            status_code in TRANSIENT_API_STATUS_CODES
            or 500 <= status_code <= 599
        )
    )
