import json
import sys
import time
import threading

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
# ATLAS IMPORTS
# ---------------------------------------------------------

try:
    from core.atlas import Atlas

    ATLAS_AVAILABLE = True

except Exception as error:
    ATLAS_AVAILABLE = False
    print("ATLAS CORE IMPORT ERROR:", error)


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


# ---------------------------------------------------------
# ATLAS INSTANCE
# ---------------------------------------------------------

atlas = None

if ATLAS_AVAILABLE:

    try:
        atlas = Atlas()

    except Exception as error:
        print("ATLAS INITIALIZATION ERROR:", error)
        atlas = None
        ATLAS_AVAILABLE = False


# ---------------------------------------------------------
# SERVER STATE
# ---------------------------------------------------------

START_TIME = time.time()

LOGS = []

LOG_LOCK = threading.Lock()


# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

def add_log(message):

    timestamp = time.strftime("%H:%M:%S")

    entry = {
        "time": timestamp,
        "message": message,
    }

    with LOG_LOCK:

        LOGS.append(entry)

        if len(LOGS) > 50:
            LOGS.pop(0)


# ---------------------------------------------------------
# MEMORY
# ---------------------------------------------------------

def get_memory_count():

    if not MEMORY_AVAILABLE:
        return 0

    try:

        memories = get_all_memories()

        if not memories:
            return 0

        return len(memories)

    except Exception:

        return 0


# ---------------------------------------------------------
# SYSTEM DATA
# ---------------------------------------------------------

def get_system_data():

    cpu = psutil.cpu_percent(interval=None)

    memory = psutil.virtual_memory()

    return {
        "cpu": round(cpu, 1),
        "ram": round(memory.percent, 1),
        "ram_used_gb": round(
            memory.used / (1024 ** 3),
            2
        ),
        "ram_total_gb": round(
            memory.total / (1024 ** 3),
            2
        ),
    }


# ---------------------------------------------------------
# ATLAS STATUS
# ---------------------------------------------------------

def get_status():

    uptime_seconds = int(
        time.time() - START_TIME
    )

    return {

        "core": (
            "ONLINE"
            if ATLAS_AVAILABLE and atlas
            else "OFFLINE"
        ),

        "ai": (
            "READY"
            if AI_AVAILABLE
            else "OFFLINE"
        ),

        "memory": (
            "ACTIVE"
            if MEMORY_AVAILABLE
            else "OFFLINE"
        ),

        "tools": "NOT CONNECTED",

        "memory_count": get_memory_count(),

        "uptime": uptime_seconds,

        "system": get_system_data(),

    }


# ---------------------------------------------------------
# JSON RESPONSE
# ---------------------------------------------------------

def send_json(handler, data, status=200):

    payload = json.dumps(
        data
    ).encode("utf-8")

    handler.send_response(status)

    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8",
    )

    handler.send_header(
        "Content-Length",
        str(len(payload)),
    )

    handler.send_header(
        "Cache-Control",
        "no-cache",
    )

    handler.end_headers()

    handler.wfile.write(payload)


# ---------------------------------------------------------
# READ REQUEST BODY
# ---------------------------------------------------------

def read_json_body(handler):

    try:

        content_length = int(
            handler.headers.get(
                "Content-Length",
                0
            )
        )

        body = handler.rfile.read(
            content_length
        )

        return json.loads(
            body.decode("utf-8")
        )

    except Exception:

        return None


# ---------------------------------------------------------
# REQUEST HANDLER
# ---------------------------------------------------------

class AtlasHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        return


    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def do_GET(self):

        if self.path == "/api/status":

            send_json(
                self,
                get_status()
            )

            return


        if self.path == "/api/logs":

            with LOG_LOCK:
                logs = list(LOGS)

            send_json(
                self,
                {
                    "logs": logs
                }
            )

            return


        if self.path == "/" or self.path == "/index.html":

            self.serve_file(
                UI_DIR / "index.html",
                "text/html"
            )

            return


        if self.path == "/style.css":

            self.serve_file(
                UI_DIR / "style.css",
                "text/css"
            )

            return


        if self.path == "/app.js":

            self.serve_file(
                UI_DIR / "app.js",
                "application/javascript"
            )

            return


        send_json(
            self,
            {
                "error": "Not found"
            },
            404
        )


    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    def do_POST(self):

        if self.path == "/api/chat":

            self.handle_chat()

            return


        send_json(
            self,
            {
                "error": "Not found"
            },
            404
        )


    # -----------------------------------------------------
    # CHAT
    # -----------------------------------------------------

    def handle_chat(self):

        global atlas

        data = read_json_body(self)

        if not data:

            send_json(
                self,
                {
                    "error": "Invalid JSON."
                },
                400
            )

            return


        user_input = data.get(
            "message",
            ""
        ).strip()


        if not user_input:

            send_json(
                self,
                {
                    "error": "Message cannot be empty."
                },
                400
            )

            return


        if not ATLAS_AVAILABLE or atlas is None:

            send_json(
                self,
                {
                    "error": "ATLAS Core is unavailable."
                },
                503
            )

            return


        add_log(
            f"USER INPUT: {user_input}"
        )


        try:

            response = atlas.process(
                user_input
            )


            if response is None:

                response = (
                    "ATLAS Core returned no response."
                )


            response = str(response)


            add_log(
                "ATLAS RESPONSE GENERATED"
            )


            send_json(
                self,
                {
                    "response": response
                }
            )


        except Exception as error:

            print(
                "ATLAS PROCESS ERROR:",
                error
            )

            add_log(
                "ATLAS PROCESS ERROR"
            )


            send_json(
                self,
                {
                    "error": (
                        "ATLAS Core encountered "
                        "an internal error."
                    )
                },
                500
            )


    # -----------------------------------------------------
    # STATIC FILES
    # -----------------------------------------------------

    def serve_file(
        self,
        path,
        content_type
    ):

        if not path.exists():

            send_json(
                self,
                {
                    "error": "File not found"
                },
                404
            )

            return


        content = path.read_bytes()

        self.send_response(200)

        self.send_header(
            "Content-Type",
            content_type
        )

        self.send_header(
            "Content-Length",
            str(len(content))
        )

        self.end_headers()

        self.wfile.write(content)


# ---------------------------------------------------------
# START SERVER
# ---------------------------------------------------------

def main():

    add_log(
        "ATLAS HUD SERVER INITIALIZED"
    )


    if ATLAS_AVAILABLE and atlas:

        add_log(
            "ATLAS CORE CONNECTED"
        )

    else:

        add_log(
            "ATLAS CORE UNAVAILABLE"
        )


    if MEMORY_AVAILABLE:

        add_log(
            "MEMORY MODULE CONNECTED"
        )

    else:

        add_log(
            "MEMORY MODULE UNAVAILABLE"
        )


    if AI_AVAILABLE:

        add_log(
            "AI MODULE DETECTED"
        )

    else:

        add_log(
            "AI MODULE UNAVAILABLE"
        )


    add_log(
        "SYSTEM TELEMETRY ONLINE"
    )


    server = ThreadingHTTPServer(
        ("127.0.0.1", 8000),
        AtlasHandler
    )


    print()
    print("========================================")
    print("           ATLAS HUD SERVER")
    print("========================================")
    print()
    print("ATLAS HUD ONLINE")
    print()
    print("Open:")
    print("http://127.0.0.1:8000")
    print()
    print("Press CTRL+C to shut down.")
    print()


    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print("ATLAS HUD SERVER OFFLINE")

    finally:

        server.server_close()


if __name__ == "__main__":

    main()