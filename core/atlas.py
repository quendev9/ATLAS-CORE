from ai.model import ask_gemini

from memory.manager import (
    process_memory,
    remember_memory,
    recall_memory,
    get_memories,
    query_memory
)

from core.identity import ATLAS_IDENTITY
from core.router import classify_input


class Atlas:

    def __init__(self):

        print("ATLAS CORE INITIALIZING")

    def process(self, user_input):
        """
        Main coordinator for ATLAS.

        Atlas determines what type of request
        it received and sends the request to
        the appropriate subsystem.
        """

        # -----------------------------------
        # CLEAN INPUT
        # -----------------------------------

        user_input = user_input.strip()

        if not user_input:

            return "Please enter a message."

        # -----------------------------------
        # ROUTE REQUEST
        # -----------------------------------

        request_type = classify_input(
            user_input
        )

        # -----------------------------------
        # EMPTY
        # -----------------------------------

        if request_type == "EMPTY":

            return "Please enter a message."

        # -----------------------------------
        # MEMORY COMMAND
        # -----------------------------------

        if request_type == "MEMORY_COMMAND":

            lowered_input = user_input.lower()

            # -------------------------------
            # REMEMBER
            # -------------------------------

            if lowered_input.startswith(
                "remember "
            ):

                memory_data = user_input[
                    len("remember "):
                ].strip()

                if " is " not in memory_data:

                    return (
                        "Tell me what to remember "
                        "using 'remember X is Y'."
                    )

                key, value = memory_data.split(
                    " is ",
                    1
                )

                key = key.strip()

                value = value.strip()

                if not key or not value:

                    return (
                        "Tell me both the memory "
                        "key and its value."
                    )

                remember_memory(
                    key,
                    value
                )

                return "I'll remember that."

            # -------------------------------
            # RECALL
            # -------------------------------

            if lowered_input.startswith(
                "recall "
            ):

                key = user_input[
                    len("recall "):
                ].strip()

                if not key:

                    return (
                        "Tell me what you want "
                        "me to recall."
                    )

                value = recall_memory(key)

                if value is None:

                    return (
                        "I don't have that "
                        "in my memory."
                    )

                return value

        # -----------------------------------
        # MEMORY QUERY
        # -----------------------------------

        if request_type == "MEMORY_QUERY":

            memory_response = query_memory(
                user_input
            )

            if memory_response is not None:

                return memory_response

        # -----------------------------------
        # MEMORY STATEMENT
        # -----------------------------------

        if request_type == "MEMORY_STATEMENT":

            memory_result = process_memory(
                user_input
            )

            if memory_result:

                return (
                    "Got it. I'll remember that."
                )

        # -----------------------------------
        # AI REQUEST
        # -----------------------------------

        if request_type == "AI_REQUEST":

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

            prompt = f"""
{ATLAS_IDENTITY}

{memory_context}

User message:
{user_input}
"""

            return ask_gemini(prompt)

        # -----------------------------------
        # FALLBACK
        # -----------------------------------

        return (
            "I'm not sure how to handle "
            "that request."
        )