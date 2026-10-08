import threading
import time
from collections import deque


_MAX_LOG_HISTORY = 50
_EVENTS = deque(maxlen=_MAX_LOG_HISTORY)
_EVENTS_LOCK = threading.Lock()


def log_event(message):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Event message must be a non-empty string.")

    entry = {
        "time": time.strftime("%H:%M:%S"),
        "message": message,
    }

    with _EVENTS_LOCK:
        _EVENTS.append(entry)


def get_events():
    with _EVENTS_LOCK:
        return list(_EVENTS)
