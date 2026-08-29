from ai.model import ask_gemini
from memory.memory import remember, recall, get_all_memories
from memory.manager import process_memory
from core.identity import ATLAS_IDENTITY


class Atlas:

    def __init__(self):
        print("ATLAS CORE INITIALIZING")

    def process(self, user_input):

        if user_input.lower().startswith("remember "):
            memory_data = user_input[9:]

            if " is " in memory_data:
                key, value = memory_data.split(" is ", 1)

                remember(key.strip(), value.strip())

                return "I'll remember that."

            return "Tell me what to remember using 'remember X is Y'."

        if user_input.lower().startswith("recall "):
            key = user_input[7:].strip()

            value = recall(key)

            if value:
                return value

            return "I don't have that in my memory."

        process_memory(user_input)

        memories = get_all_memories()

        memory_context = ""

        if memories:
            memory_context = (
                "\n\nRelevant information I remember about the user:\n"
            )

            for key, value in memories.items():
                memory_context += f"- {key}: {value}\n"

        prompt = f"""
{ATLAS_IDENTITY}

{memory_context}

User message:
{user_input}
"""

        return ask_gemini(prompt)