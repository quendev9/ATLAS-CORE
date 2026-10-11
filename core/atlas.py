import re

from ai.model import ask_gemini, is_transient_api_error

from memory.manager import (
    remember_memory,
    recall_memory,
    query_memory,
    extract_facts,
    save_fact,
)
from memory.conversations import (
    add_message,
    create_conversation,
    get_active_conversation_id,
    get_conversation,
)
from core.commands import handle_deterministic_command
from core.context_builder import build_context
from core.identity import ATLAS_IDENTITY
from core.router import classify_input
from core.event_logger import log_event


class Atlas:

    MODEL_UNAVAILABLE_RESPONSE = (
        "I'm having trouble reaching Gemini right now. "
        "Please try again in a moment."
    )

    def __init__(self):
        print("ATLAS CORE INITIALIZING")
        self.state = "idle"
        self.active_project = "ATLAS"
        self.active_conversation_id = get_active_conversation_id()

        conversation = (
            get_conversation(self.active_conversation_id)
            if self.active_conversation_id
            else None
        )

        if conversation is None:
            conversation = create_conversation(
                title="Default conversation",
                project=self.active_project,
            )
            self.active_conversation_id = conversation["id"]
        else:
            self.active_project = (
                conversation.get("project") or self.active_project
            )

    def _record_message(
        self,
        role,
        content,
        conversation_id=None,
        project=None,
    ):
        """Persist a message to a specific conversation."""

        target_id = conversation_id or self.active_conversation_id

        if not target_id or get_conversation(target_id) is None:
            conversation = create_conversation(
                title="Default conversation",
                project=self.active_project,
            )
            target_id = conversation["id"]
            self.active_conversation_id = target_id

        target_project = (
            project if project is not None else self.active_project
        )

        return add_message(
            target_id,
            role,
            str(content),
            project=target_project,
        )

    def _capture_automatic_memories(self, user_input, project):
        """
        Extract durable facts and route them to the appropriate
        memory system.

        Personal facts belong in personal memory.
        Facts about named entities and project relationships belong
        in project memory.
        """

        facts = extract_facts(user_input)
        saved = []

        for fact in facts:
            save_fact(fact, project)
            saved.append(fact)

        return saved

    def process(self, user_input):
        """Process a user message and persist the resulting exchange."""

        if not isinstance(user_input, str):
            return "Please enter a message."

        user_input = user_input.strip()

        if not user_input:
            return "Please enter a message."

        request_type = classify_input(user_input)

        if request_type == "EMPTY":
            return "Please enter a message."

        # Capture the conversation before any command can switch it.
        source_conversation_id = self.active_conversation_id
        source_project = self.active_project

        # Record the user message exactly once.
        self._record_message(
            "user",
            user_input,
            conversation_id=source_conversation_id,
            project=source_project,
        )

        # ---------------------------------------------------------
        # DETERMINISTIC COMMANDS
        # ---------------------------------------------------------

        local_command_result = handle_deterministic_command(
            self,
            user_input,
        )

        if local_command_result is not None:
            self._record_message(
                "assistant",
                local_command_result,
                conversation_id=source_conversation_id,
                project=source_project,
            )
            return local_command_result

        # ---------------------------------------------------------
        # EXPLICIT MEMORY COMMANDS
        # ---------------------------------------------------------

        if request_type == "MEMORY_COMMAND":
            remember_match = re.match(
                r"^remember\s+(.+?)\s+is\s+(.+)$",
                user_input,
                re.IGNORECASE,
            )

            if remember_match:
                key = remember_match.group(1).strip()
                value = remember_match.group(2).strip()

                if not key or not value:
                    response = (
                        "Tell me both the memory key and its value."
                    )
                else:
                    remember_memory(key, value)
                    response = "I'll remember that."

                self._record_message(
                    "assistant",
                    response,
                    conversation_id=source_conversation_id,
                    project=source_project,
                )
                return response

            recall_match = re.match(
                r"^recall\s+(.+)$",
                user_input,
                re.IGNORECASE,
            )

            if recall_match:
                key = recall_match.group(1).strip()

                if not key:
                    response = "Tell me what you want me to recall."
                else:
                    value = recall_memory(key)
                    response = (
                        value
                        if value is not None
                        else "I don't have that in my memory."
                    )

                self._record_message(
                    "assistant",
                    response,
                    conversation_id=source_conversation_id,
                    project=source_project,
                )
                return response

            response = (
                "Use memory commands like "
                "'remember X is Y' or 'recall X'."
            )
            self._record_message(
                "assistant",
                response,
                conversation_id=source_conversation_id,
                project=source_project,
            )
            return response

        # ---------------------------------------------------------
        # MEMORY QUERIES
        # ---------------------------------------------------------

        if request_type == "MEMORY_QUERY":
            memory_response = query_memory(
                user_input,
                project_name=source_project,
            )

            if memory_response is not None:
                self._record_message(
                    "assistant",
                    memory_response,
                    conversation_id=source_conversation_id,
                    project=source_project,
                )
                return memory_response

        # ---------------------------------------------------------
        # AUTOMATIC MEMORY CAPTURE
        # ---------------------------------------------------------

        self._capture_automatic_memories(
            user_input,
            source_project,
        )

        # ---------------------------------------------------------
        # BUILD AI CONTEXT
        # ---------------------------------------------------------

        conversation = get_conversation(source_conversation_id)

        if conversation:
            context = build_context(
                source_conversation_id,
                user_input,
                project_name=source_project,
                max_recent_messages=8,
                max_memory_facts=6,
            )

            prompt = (
                f"{ATLAS_IDENTITY}\n\n"
                f"{context}"
            )
        else:
            prompt = (
                f"{ATLAS_IDENTITY}\n\n"
                f"User message:\n{user_input}\n"
            )

        # ---------------------------------------------------------
        # AI RESPONSE
        # ---------------------------------------------------------

        log_event("AI REQUEST STARTED")

        try:
            response = ask_gemini(
                prompt,
                conversation_id=source_conversation_id,
            )

        except Exception as error:
            status_code = getattr(error, "status_code", None)

            if not isinstance(status_code, int) or isinstance(
                status_code, bool
            ):
                status_code = getattr(error, "code", None)

            if (
                isinstance(status_code, int)
                and not isinstance(status_code, bool)
                and 100 <= status_code <= 599
            ):
                failure_message = f"AI REQUEST FAILED - {status_code}"
            else:
                failure_message = (
                    f"AI REQUEST FAILED - {type(error).__name__}"
                )

            log_event(failure_message)

            try:
                self._record_message(
                    "error",
                    failure_message,
                    conversation_id=source_conversation_id,
                    project=source_project,
                )
            except Exception:
                log_event("FAILED TO SAVE AI ERROR TO CONVERSATION")

            self._record_message(
                "assistant",
                self.MODEL_UNAVAILABLE_RESPONSE,
                conversation_id=source_conversation_id,
                project=source_project,
            )
            if is_transient_api_error(error):
                log_event("AI RESPONSE FALLBACK")
            else:
                log_event("AI RESPONSE FALLBACK - NON-TRANSIENT FAILURE")
            self.state = "ready"
            return self.MODEL_UNAVAILABLE_RESPONSE

        if not isinstance(response, str):
            response = str(response)

        # Save the assistant response to the same conversation as
        # the user's message, even if the active conversation changed.
        self._record_message(
            "assistant",
            response,
            conversation_id=source_conversation_id,
            project=source_project,
        )

        log_event("AI RESPONSE RECEIVED")
        self.state = "ready"
        return response