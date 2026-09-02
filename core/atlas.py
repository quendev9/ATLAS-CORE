from ai.model import ask_gemini
from memory.manager import (
    process_memory,
    remember_memory,
    recall_memory,
    get_memories
)
from core.identity import ATLAS_IDENTITY


class Atlas:

    def __init__(self):
        print("ATLAS CORE INITIALIZING")

    def process(self, user_input):
        """
        Main coordinator for ATLAS.

        Atlas coordinates the different systems,
        but does not handle their internal logic.
        """

        # -----------------------------------
        # CLEAN INPUT
        # -----------------------------------

        user_input = user_input.strip()

        if not user_input:
            return "Please enter a message."

        lowered_input = user_input.lower()

        # -----------------------------------
        # EXPLICIT MEMORY COMMAND
        # -----------------------------------

        if lowered_input.startswith("remember "):

            memory_data = user_input[9:].strip()

            if " is " not in memory_data:
                return (
                    "Tell me what to remember using "
                    "'remember X is Y'."
                )

            key, value = memory_data.split(" is ", 1)

            key = key.strip()
            value = value.strip()

            remember_memory(
                key,
                value
            )

            return "I'll remember that."

        # -----------------------------------
        # RECALL COMMAND
        # -----------------------------------

        if lowered_input.startswith("recall "):

            key = user_input[7:].strip()

            value = recall_memory(key)

            if value is None:
                return "I don't have that in my memory."

            return value

        # -----------------------------------
        # AUTOMATIC MEMORY
        # -----------------------------------

        memory_result = process_memory(user_input)

        if memory_result:

            return "Got it. I'll remember that."

        # -----------------------------------
        # MEMORY CONTEXT
        # -----------------------------------

        memories = get_memories()

        memory_context = ""

        if memories:

            memory_context = (
                "\n\nInformation I remember "
                "about the user:\n"
            )

            for memory in memories:

                memory_context += (
                    f"- {memory['key']}: "
                    f"{memory['value']}\n"
                )

        # -----------------------------------
        # BUILD AI REQUEST
        # -----------------------------------

        prompt = f"""
{ATLAS_IDENTITY}

{memory_context}

User message:
{user_input}
"""

        # -----------------------------------
        # AI
        # -----------------------------------

        return ask_gemini(prompt)