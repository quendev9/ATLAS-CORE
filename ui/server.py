
import json
import os
import queue
import sys
import threading
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psutil


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

UI_DIR = Path(__file__).parent
PROJECT_DIR = UI_DIR.parent

sys.path.insert(0, str(PROJECT_DIR))


# ---------------------------------------------------------
# LEWIS IMPORTS
# ---------------------------------------------------------

from core.event_logger import get_events, log_event
from memory.conversations import (
    create_conversation,
    get_active_conversation_id,
    get_conversation,
    list_conversations,
    set_active_conversation,
)

try:
    from core.lewis import Lewis
    LEWIS_AVAILABLE = True
except Exception as error:
    LEWIS_AVAILABLE = False
    print("LEWIS CORE IMPORT ERROR:", type(error).__name__)

try:
    from memory.memory import get_all_memories
    MEMORY_AVAILABLE = True
except Exception:
    MEMORY_AVAILABLE = False

try:
    import ai.model
    AI_AVAILABLE = True
except Exception:
    AI_AVAILABLE = False

try:
    from voice.speech_input import listen_once
    VOICE_INPUT_AVAILABLE = True
except Exception as error:
    VOICE_INPUT_AVAILABLE = False
    print("LEWIS VOICE INPUT IMPORT ERROR:", type(error).__name__, str(error))

try:
    from voice.speech_output import speak, stop_speaking, was_stop_requested
    VOICE_OUTPUT_AVAILABLE = True
except Exception as error:
    VOICE_OUTPUT_AVAILABLE = False
    print("LEWIS VOICE OUTPUT IMPORT ERROR:", type(error).__name__, str(error))


# ---------------------------------------------------------
# LEWIS INSTANCE
# ---------------------------------------------------------

lewis = None

if LEWIS_AVAILABLE:
    try:
        lewis = Lewis()
    except Exception as error:
        print("LEWIS INITIALIZATION ERROR:", type(error).__name__)
        lewis = None
        LEWIS_AVAILABLE = False


# ---------------------------------------------------------
# SERVER STATE AND LOCKS
# ---------------------------------------------------------

START_TIME = time.time()

# Only one request may process a message through the shared
# Lewis instance at a time.
core_lock = threading.Lock()

# Only one microphone session may run at a time.
voice_lock = threading.Lock()

# Protect shared status and voice-result values.
state_lock = threading.Lock()

voice_stop_event = threading.Event()
voice_interrupt_event = threading.Event()
pending_speech = queue.Queue(maxsize=20)

server_state = {
    "activity": "READY",
    "voice_available": VOICE_INPUT_AVAILABLE,
    "voice_enabled": True,
    "listening": False,
    "speaking": False,
    "processing": False,
    "voice_session_active": False,
    "voice_session_stopping": False,
    "voice_event_id": 0,
    "voice_response_id": 0,
    "last_transcript": "",
    "last_response": "",
    "last_error": "",
}


def update_state(**changes):
    with state_lock:
        server_state.update(changes)
        if server_state["voice_session_stopping"]:
            server_state["activity"] = "STOPPING"
        elif server_state["speaking"]:
            server_state["activity"] = "SPEAKING"
        elif server_state["processing"]:
            server_state["activity"] = "PROCESSING"
        elif server_state["listening"]:
            server_state["activity"] = "LISTENING"
        else:
            server_state["activity"] = "READY"


def get_state_snapshot():
    with state_lock:
        return dict(server_state)


# ---------------------------------------------------------
# MEMORY
# ---------------------------------------------------------

def get_memory_count():
    if not MEMORY_AVAILABLE:
        return None

    try:
        return len(get_all_memories())
    except Exception as error:
        print("LEWIS MEMORY STATUS ERROR:", type(error).__name__)
        return None


# ---------------------------------------------------------
# SYSTEM DATA
# ---------------------------------------------------------

def get_system_data():
    cpu = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()

    return {
        "cpu": round(cpu, 1),
        "ram": round(memory.percent, 1),
        "ram_used_gb": round(memory.used / (1024 ** 3), 2),
        "ram_total_gb": round(memory.total / (1024 ** 3), 2),
    }


# ---------------------------------------------------------
# LEWIS STATUS
# ---------------------------------------------------------

def get_status():
    state = get_state_snapshot()
    memory_count = get_memory_count()
    ai_info = ai.model.get_ai_provider_info() if AI_AVAILABLE else None

    return {
        "core": (
            "ONLINE" if LEWIS_AVAILABLE and lewis else "OFFLINE"
        ),
        "ai": (
            "CONFIGURED"
            if ai_info and ai_info["configured"]
            else "NOT CONFIGURED" if AI_AVAILABLE else "OFFLINE"
        ),
        "ai_provider": (
            ai_info["provider"] if ai_info else "Unavailable"
        ),
        "ai_model": ai_info["model"] if ai_info else None,
        "ai_selection": (
            ai_info["selection"] if ai_info else None
        ),
        "ai_models": (
            ai.model.get_available_ai_models() if AI_AVAILABLE else []
        ),
        "memory": (
            "ACTIVE" if memory_count is not None
            else "ERROR" if MEMORY_AVAILABLE else "OFFLINE"
        ),
        "tools": "NOT CONNECTED",
        "memory_count": memory_count,
        "uptime": int(time.time() - START_TIME),
        "system": get_system_data(),
        "activity": state["activity"],
        "processing": state["processing"],
        "voice_available": state["voice_available"],
        "voice_output_available": VOICE_OUTPUT_AVAILABLE,
        "voice_enabled": state["voice_enabled"],
        "listening": state["listening"],
        "speaking": state["speaking"],
        "voice_session_active": state["voice_session_active"],
        "voice_session_stopping": state["voice_session_stopping"],
        "voice_event_id": state["voice_event_id"],
        "voice_response_id": state["voice_response_id"],
        "last_transcript": state["last_transcript"],
        "last_response": state["last_response"],
        "last_error": state["last_error"],
    }


# ---------------------------------------------------------
# JSON HELPERS
# ---------------------------------------------------------

def send_json(handler, data, status=200):
    payload = json.dumps(data).encode("utf-8")

    handler.send_response(status)
    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8",
    )
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()

    try:
        handler.wfile.write(payload)
    except (BrokenPipeError, ConnectionResetError):
        pass


def read_json_body(handler):
    try:
        content_length = int(handler.headers.get("Content-Length", "0"))

        if content_length <= 0 or content_length > 100_000:
            return None

        body = handler.rfile.read(content_length)
        data = json.loads(body.decode("utf-8"))

        return data if isinstance(data, dict) else None

    except (ValueError, UnicodeError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------
# CORE PROCESSING
# ---------------------------------------------------------

def process_with_lewis(user_input):
    if not LEWIS_AVAILABLE or lewis is None:
        raise RuntimeError("LEWIS Core is unavailable.")

    with core_lock:
        update_state(processing=True)

        try:
            response = lewis.process(user_input)

            if response is None:
                response = "LEWIS Core returned no response."

            return str(response)

        finally:
            update_state(processing=False)


# ---------------------------------------------------------
# VOICE WORKER
# ---------------------------------------------------------

def _speak_session_text(text, stop_event):
    if stop_event.is_set():
        return

    def playback_started():
        update_state(processing=False, speaking=True)
        log_event("VOICE OUTPUT STARTED")

    try:
        update_state(processing=True, speaking=False)
        completed = speak(
            text,
            cancel_event=stop_event,
            on_playback_start=playback_started,
        )
    finally:
        update_state(processing=False, speaking=False)

    if not completed and not stop_event.is_set():
        update_state(last_error="Speech output could not be completed.")
        log_event("VOICE OUTPUT FAILED")
    log_event("VOICE OUTPUT FINISHED")


def _speak_pending_text(stop_event):
    try:
        text = pending_speech.get_nowait()
    except queue.Empty:
        return False

    try:
        _speak_session_text(text, stop_event)
    finally:
        pending_speech.task_done()

    return True


def voice_worker(stop_event):
    try:
        log_event("VOICE LISTENING STARTED")

        while not stop_event.is_set():
            voice_interrupt_event.clear()

            if _speak_pending_text(stop_event):
                continue

            if stop_event.is_set():
                break

            try:
                transcript = listen_once(
                    stop_event=stop_event,
                    interrupt_event=voice_interrupt_event,
                    on_capture_start=lambda: update_state(listening=True),
                )
            finally:
                update_state(listening=False)

            if stop_event.is_set():
                break

            if not transcript or not transcript.strip():
                log_event("VOICE INPUT EMPTY OR TIMED OUT")
                if not voice_interrupt_event.is_set():
                    stop_event.wait(0.5)
                continue

            transcript = transcript.strip()
            with state_lock:
                server_state["voice_event_id"] += 1
                event_id = server_state["voice_event_id"]
            update_state(
                last_transcript=transcript,
                last_response="",
                voice_response_id=0,
            )
            log_event("VOICE INPUT RECOGNIZED")

            response = process_with_lewis(transcript)
            update_state(
                last_response=response,
                voice_response_id=event_id,
            )
            log_event("VOICE RESPONSE GENERATED")

            state = get_state_snapshot()
            if (
                state["voice_enabled"]
                and VOICE_OUTPUT_AVAILABLE
                and not stop_event.is_set()
            ):
                _speak_session_text(response, stop_event)

    except Exception as error:
        print("LEWIS VOICE ERROR:", type(error).__name__)
        log_event("VOICE OPERATION FAILED")

        update_state(
            listening=False,
            speaking=False,
            last_error=(
                "Voice operation failed: "
                f"{type(error).__name__}. Check the server terminal."
            ),
        )

    finally:
        update_state(
            listening=False,
            speaking=False,
            voice_session_active=False,
            voice_session_stopping=False,
        )
        voice_lock.release()


def start_voice_listening():
    if not VOICE_INPUT_AVAILABLE:
        return False, "Voice input modules are unavailable."

    if not LEWIS_AVAILABLE or lewis is None:
        return False, "LEWIS Core is unavailable."

    if not voice_lock.acquire(blocking=False):
        return False, "A voice operation is already running."

    try:
        voice_stop_event.clear()
        voice_interrupt_event.clear()
        while True:
            try:
                pending_speech.get_nowait()
                pending_speech.task_done()
            except queue.Empty:
                break
        update_state(
            voice_session_active=True,
            voice_session_stopping=False,
            listening=False,
            speaking=False,
            last_error="",
            last_transcript="",
            last_response="",
        )
        worker = threading.Thread(
            target=voice_worker,
            args=(voice_stop_event,),
            name="LEWIS-Voice-Worker",
            daemon=True,
        )
        worker.start()
        return True, "Voice session started."

    except Exception:
        voice_lock.release()
        update_state(
            listening=False,
            speaking=False,
            voice_session_active=False,
            voice_session_stopping=False,
            last_error="Could not start the voice worker.",
        )
        return False, "Could not start the voice worker."


def stop_voice_session():
    with state_lock:
        if not server_state["voice_session_active"]:
            return False
        voice_stop_event.set()
        server_state["voice_session_stopping"] = True
        server_state["activity"] = "STOPPING"

    voice_interrupt_event.set()
    if VOICE_OUTPUT_AVAILABLE:
        stop_speaking()
    log_event("VOICE SESSION STOP REQUESTED")
    return True


# ---------------------------------------------------------
# HTTP REQUEST HANDLER
# ---------------------------------------------------------

class LewisHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        return

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/status":
            send_json(self, get_status())
            return

        if path == "/api/logs":
            send_json(self, {"logs": get_events()})
            return

        if path == "/api/conversations":
            conversations = list_conversations()
            send_json(
                self,
                {
                    "conversations": [
                        {
                            "id": item["id"],
                            "title": item["title"],
                            "updated_at": item["updated_at"],
                        }
                        for item in conversations
                    ],
                    "active_id": get_active_conversation_id(),
                },
            )
            return

        if path.startswith("/api/conversations/"):
            conversation_id = path[len("/api/conversations/"):]
            conversation = get_conversation(conversation_id)
            if conversation is None:
                send_json(self, {"error": "Conversation not found."}, 404)
            else:
                send_json(self, {"conversation": conversation})
            return

        if path in ("/", "/index.html"):
            self.serve_file(UI_DIR / "index.html", "text/html")
            return

        if path == "/style.css":
            self.serve_file(UI_DIR / "style.css", "text/css")
            return

        if path == "/app.js":
            self.serve_file(
                UI_DIR / "app.js",
                "application/javascript",
            )
            return

        if path == "/lewis-logo.svg":
            self.serve_file(UI_DIR / "lewis-logo.svg", "image/svg+xml")
            return

        send_json(self, {"error": "Not found"}, 404)

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/chat":
            self.handle_chat()
            return

        if path == "/api/ai/model":
            self.handle_ai_model_selection()
            return

        if path == "/api/conversations":
            self.handle_conversation_create()
            return

        if path == "/api/conversations/select":
            self.handle_conversation_select()
            return

        if path == "/api/voice/listen":
            self.handle_voice_listen()
            return

        if path == "/api/voice/session/start":
            self.handle_voice_listen()
            return

        if path == "/api/voice/session/stop":
            self.handle_voice_session_stop()
            return

        if path == "/api/voice/speak":
            self.handle_voice_speak()
            return

        if path == "/api/voice/stop":
            self.handle_voice_stop()
            return

        if path == "/api/voice/settings":
            self.handle_voice_settings()
            return

        send_json(self, {"error": "Not found"}, 404)

    # -----------------------------------------------------
    # TEXT CHAT
    # -----------------------------------------------------

    def handle_conversation_create(self):
        data = read_json_body(self)
        if data is None:
            send_json(self, {"error": "Invalid JSON."}, 400)
            return
        if not LEWIS_AVAILABLE or lewis is None:
            send_json(self, {"error": "LEWIS Core is unavailable."}, 503)
            return

        title = data.get("title", "New conversation")
        if not isinstance(title, str) or len(title.strip()) > 120:
            send_json(self, {"error": "Conversation title is invalid."}, 400)
            return

        try:
            conversation = create_conversation(
                title=title.strip() or "New conversation",
                project=lewis.active_project,
            )
            lewis.active_conversation_id = conversation["id"]
            send_json(self, {"conversation": conversation}, 201)
        except Exception as error:
            print("LEWIS CONVERSATION CREATE ERROR:", type(error).__name__)
            send_json(
                self,
                {"error": "Could not create a conversation."},
                500,
            )

    def handle_conversation_select(self):
        data = read_json_body(self)
        if data is None or not isinstance(data.get("id"), str):
            send_json(self, {"error": "Provide a conversation ID."}, 400)
            return
        if not LEWIS_AVAILABLE or lewis is None:
            send_json(self, {"error": "LEWIS Core is unavailable."}, 503)
            return

        conversation = get_conversation(data["id"])
        if conversation is None:
            send_json(self, {"error": "Conversation not found."}, 404)
            return

        try:
            set_active_conversation(conversation["id"])
            lewis.active_conversation_id = conversation["id"]
            lewis.active_project = (
                conversation.get("project") or lewis.active_project
            )
            send_json(self, {"conversation": conversation})
        except Exception as error:
            print("LEWIS CONVERSATION SELECT ERROR:", type(error).__name__)
            send_json(
                self,
                {"error": "Could not open the conversation."},
                500,
            )

    def handle_ai_model_selection(self):
        data = read_json_body(self)

        if data is None:
            send_json(self, {"error": "Invalid JSON."}, 400)
            return

        if not AI_AVAILABLE:
            send_json(self, {"error": "AI module is unavailable."}, 503)
            return

        try:
            selection = ai.model.set_ai_selection(
                data.get("provider"),
                data.get("model"),
            )
        except ValueError as error:
            send_json(self, {"error": str(error)}, 400)
            return

        log_event(
            "AI MODEL SELECTED - "
            f"{selection['provider']} / {selection['model']}"
        )
        send_json(self, {"selection": selection})

    def handle_chat(self):
        data = read_json_body(self)

        if data is None:
            send_json(self, {"error": "Invalid JSON."}, 400)
            return

        user_input = data.get("message", "")

        if not isinstance(user_input, str):
            send_json(self, {"error": "Message must be text."}, 400)
            return

        user_input = user_input.strip()

        if not user_input:
            send_json(self, {"error": "Message cannot be empty."}, 400)
            return

        if len(user_input) > 10_000:
            send_json(self, {"error": "Message is too long."}, 400)
            return

        if not LEWIS_AVAILABLE or lewis is None:
            send_json(
                self,
                {"error": "LEWIS Core is unavailable."},
                503,
            )
            return

        log_event("USER INPUT RECEIVED")
        log_event("REQUEST PROCESSING")

        try:
            response = process_with_lewis(user_input)

        except Exception as error:
            print("LEWIS PROCESS ERROR:", type(error).__name__)
            log_event("LEWIS PROCESS FAILED")

            send_json(
                self,
                {"error": "LEWIS Core encountered an internal error."},
                500,
            )
            return

        log_event("LEWIS PROCESS COMPLETED")
        send_json(self, {"response": response})
        log_event("RESPONSE DELIVERED")

    # -----------------------------------------------------
    # START VOICE LISTENING
    # -----------------------------------------------------

    def handle_voice_listen(self):
        success, message = start_voice_listening()

        if not success:
            send_json(self, {"error": message}, 409)
            return

        send_json(
            self,
            {
                "message": message,
                "activity": get_state_snapshot()["activity"],
                "voice_session_active": True,
            },
            202,
        )

    def handle_voice_session_stop(self):
        if not VOICE_INPUT_AVAILABLE:
            send_json(
                self,
                {"error": "Voice input modules are unavailable."},
                503,
            )
            return

        if not stop_voice_session():
            send_json(
                self,
                {
                    "message": "No voice session is running.",
                    "activity": get_state_snapshot()["activity"],
                    "voice_session_active": False,
                },
            )
            return

        send_json(
            self,
            {
                "message": "Voice session stopping.",
                "activity": "STOPPING",
                "voice_session_active": True,
            },
            202,
        )

    # -----------------------------------------------------
    # SPEAK TEXT THROUGH LEWIS VOICE
    # -----------------------------------------------------

    def handle_voice_speak(self):
        data = read_json_body(self)

        if data is None:
            send_json(self, {"error": "Invalid JSON."}, 400)
            return

        text = data.get("text", "")

        if not isinstance(text, str) or not text.strip():
            send_json(self, {"error": "Text cannot be empty."}, 400)
            return

        text = text.strip()

        if len(text) > 10_000:
            send_json(self, {"error": "Text is too long."}, 400)
            return

        if not VOICE_OUTPUT_AVAILABLE:
            send_json(
                self,
                {"error": "Voice output modules are unavailable."},
                503,
            )
            return

        state = get_state_snapshot()

        if not state["voice_enabled"]:
            send_json(self, {"error": "Voice output is disabled."}, 409)
            return

        if state["voice_session_active"]:
            if state["voice_session_stopping"]:
                send_json(
                    self,
                    {"error": "The voice session is stopping."},
                    409,
                )
                return

            try:
                pending_speech.put_nowait(text)
            except queue.Full:
                send_json(
                    self,
                    {"error": "The voice response queue is full."},
                    429,
                )
                return

            voice_interrupt_event.set()
            send_json(
                self,
                {
                    "message": "Speech response queued for the voice session.",
                    "queued": True,
                },
                202,
            )
            return

        # A live microphone or output operation owns the voice device.
        if state["speaking"] or state["listening"]:
            send_json(
                self,
                {"error": "A voice operation is already running."},
                409,
            )
            return

        def speech_worker():
            def playback_started():
                update_state(processing=False, speaking=True)
                log_event("VOICE OUTPUT STARTED")

            try:
                update_state(
                    processing=True,
                    speaking=False,
                    last_error="",
                )
                completed = speak(
                    text,
                    on_playback_start=playback_started,
                )
                if not completed and not was_stop_requested():
                    update_state(
                        last_error="Speech output could not be completed."
                    )
                    log_event("VOICE OUTPUT FAILED")

            except Exception as error:
                print("LEWIS SPEECH ERROR:", type(error).__name__)
                update_state(
                    last_error=(
                        "Speech output failed: "
                        f"{type(error).__name__}."
                    ),
                )

            finally:
                update_state(
                    processing=False,
                    speaking=False,
                )

        # Reserve the voice lock so this cannot overlap microphone capture.
        if not voice_lock.acquire(blocking=False):
            send_json(
                self,
                {"error": "A voice operation is already running."},
                409,
            )
            return

        def reserved_speech_worker():
            try:
                speech_worker()
            finally:
                voice_lock.release()

        try:
            threading.Thread(
                target=reserved_speech_worker,
                name="LEWIS-Speech-Worker",
                daemon=True,
            ).start()
        except Exception:
            voice_lock.release()
            send_json(
                self,
                {"error": "Could not start speech output."},
                500,
            )
            return

        send_json(self, {"message": "Speech output started."}, 202)

    # -----------------------------------------------------
    # STOP SPEECH OUTPUT
    # -----------------------------------------------------

    def handle_voice_stop(self):
        if not VOICE_OUTPUT_AVAILABLE:
            send_json(
                self,
                {"error": "Voice output modules are unavailable."},
                503,
            )
            return

        try:
            stop_speaking()
            send_json(self, {"message": "Stop requested."})
        except Exception as error:
            print("LEWIS STOP SPEECH ERROR:", type(error).__name__)
            send_json(self, {"error": "Could not stop speech output."}, 500)

    # -----------------------------------------------------
    # VOICE SETTINGS
    # -----------------------------------------------------

    def handle_voice_settings(self):
        data = read_json_body(self)

        if data is None or not isinstance(data.get("enabled"), bool):
            send_json(
                self,
                {"error": "Provide an 'enabled' boolean."},
                400,
            )
            return

        update_state(voice_enabled=data["enabled"])

        log_event(
            "VOICE OUTPUT ENABLED"
            if data["enabled"]
            else "VOICE OUTPUT DISABLED"
        )

        send_json(
            self,
            {"voice_enabled": data["enabled"]},
        )

    # -----------------------------------------------------
    # STATIC FILES
    # -----------------------------------------------------

    def serve_file(self, path, content_type):
        if not path.exists():
            send_json(self, {"error": "File not found."}, 404)
            return

        content = path.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass


# ---------------------------------------------------------
# START SERVER
# ---------------------------------------------------------

def main():
    log_event("LEWIS HUD SERVER INITIALIZED")

    if LEWIS_AVAILABLE and lewis:
        log_event("LEWIS CORE CONNECTED")
    else:
        log_event("LEWIS CORE UNAVAILABLE")

    log_event(
        "MEMORY MODULE CONNECTED"
        if MEMORY_AVAILABLE
        else "MEMORY MODULE UNAVAILABLE"
    )

    log_event(
        "AI MODULE DETECTED"
        if AI_AVAILABLE
        else "AI MODULE UNAVAILABLE"
    )

    log_event(
        "VOICE INPUT CONNECTED"
        if VOICE_INPUT_AVAILABLE
        else "VOICE INPUT UNAVAILABLE"
    )
    log_event(
        "VOICE OUTPUT CONNECTED"
        if VOICE_OUTPUT_AVAILABLE
        else "VOICE OUTPUT UNAVAILABLE"
    )

    log_event("SYSTEM TELEMETRY ONLINE")

    server = ThreadingHTTPServer(
        ("127.0.0.1", 8000),
        LewisHandler,
    )

    print()
    print("========================================")
    print("           LEWIS HUD SERVER")
    print("========================================")
    print()
    print("LEWIS HUD ONLINE")
    print("Open: http://127.0.0.1:8000")
    print("Press CTRL+C to shut down.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        print("LEWIS HUD SERVER OFFLINE")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
