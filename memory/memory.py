import json
from pathlib import Path


MEMORY_FILE = Path(__file__).parent / "memory.json"


def load_memory():
    """
    Load all stored memories from disk.
    """

    if not MEMORY_FILE.exists():
        return {"memories": []}

    with open(MEMORY_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_memory(memory):
    """
    Save the complete memory structure to disk.
    """

    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(
            memory,
            file,
            indent=4,
            ensure_ascii=False
        )


def remember(key, value, category="other", importance=0.5):
    """
    Store a memory.

    If the key already exists, update it.
    """

    memory = load_memory()

    new_memory = {
        "key": key,
        "value": value,
        "category": category,
        "importance": importance
    }

    for stored_memory in memory["memories"]:

        if stored_memory["key"].lower() == key.lower():

            stored_memory.update(new_memory)

            save_memory(memory)

            return


    memory["memories"].append(new_memory)

    save_memory(memory)


def recall(key):
    """
    Retrieve a memory by its key.

    Returns:
        The stored value
        or None if not found.
    """

    memory = load_memory()

    for stored_memory in memory["memories"]:

        if stored_memory["key"].lower() == key.lower():

            return stored_memory["value"]

    return None


def get_all_memories():
    """
    Return every stored memory.
    """

    memory = load_memory()

    return memory["memories"]