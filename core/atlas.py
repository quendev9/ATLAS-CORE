import re

from ai.model import ask_gemini

from memory.manager import (
    remember_memory,
    recall_memory,
    get_memories,
    query_memory,
)

from memory.intelligence import evaluate_memory

from core.identity import ATLAS_IDENTITY
from core.router import classify_input


class Atlas:

    def __init__(self):
        print("ATLAS CORE INITIALIZING")

    def process(self, user_input):
        """Main coordinator for ATLAS."""

        if not isinstance(user_input, str):
            return "Please enter a message."

        user_input = user_input.strip()

        if not user_input:
            return "Please enter a message."

        request_type = classify_input(user_input)

        if request_type == "EMPTY":
            return "Please enter a message."

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
                    return "Tell me both the memory key and its value."

                remember_memory(key, value)

                return "I'll remember that."

            recall_match = re.match(
                r"^recall\s+(.+)$",
                user_input,
                re.IGNORECASE,
            )

            if recall_match:
                key = recall_match.group(1).strip()

                if not key:
                    return "Tell me what you want me to recall."

                value = recall_memory(key)

                if value is None:
                    return "I don't have that in my memory."

                return value

            return "Use memory commands like 'remember X is Y' or 'recall X'."

        # ---------------------------------------------------------
        # MEMORY QUERIES
        # ---------------------------------------------------------

        if request_type == "MEMORY_QUERY":

            memory_response = query_memory(user_input)

            if memory_response is not None:
                return memory_response

        # ---------------------------------------------------------
        # AUTOMATIC MEMORY INTELLIGENCE
        # ---------------------------------------------------------

        memory_evaluation = evaluate_memory(user_input)

        if (
            memory_evaluation
            and memory_evaluation["worth_remembering"]
            and memory_evaluation["memory"]
        ):

            memory = memory_evaluation["memory"]

            remember_memory(
                memory["key"],
                memory["value"],
                memory["category"],
            )

        # ---------------------------------------------------------
        # AI RESPONSE
        # ---------------------------------------------------------

        memories = get_memories() or []

        memory_context = ""

        for memory in memories:
            if not isinstance(memory, dict):
                continue

            key = memory.get("key", "unknown")
            value = memory.get("value", "")

            if not memory_context:
                memory_context = (
                    "\n\nInformation I remember about the user:\n"
                )

            memory_context += f"- {key}: {value}\n"

        prompt = f"""
{ATLAS_IDENTITY}
{memory_context}
User message:
{user_input}
"""

        return ask_gemini(prompt)