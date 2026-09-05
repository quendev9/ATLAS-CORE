import json
from pathlib import Path


MEMORY_FILE = Path(__file__).parent / "memory.json"

MULTI_VALUE_CATEGORIES = {
    "interest",
    "likes",
    "loves",
    "dislikes",
    "enjoys",
    "project",
    "goal",
    "aspiration",
}


def load_memory():
    """Load memories from disk safely."""
    if not MEMORY_FILE.exists():
        return {"memories": []}

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            memory = json.load(file)
    except (json.JSONDecodeError, OSError, TypeError):
        return {"memories": []}

    if not isinstance(memory, dict):
        return {"memories": []}

    if not isinstance(memory.get("memories"), list):
        memory["memories"] = []

    return memory


def save_memory(memory):
    """Save the complete memory structure to disk."""
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memory, file, indent=4, ensure_ascii=False)


def remember(key, value, category="other", importance=0.5):
    """Store a memory, updating single-value keys and preserving multi-values."""
    key = str(key).strip()
    value = str(value).strip()
    category = str(category).strip().lower()

    if not key or not value:
        return

    memory = load_memory()
    new_memory = {
        "key": key,
        "value": value,
        "category": category,
        "importance": importance,
    }

    if category in MULTI_VALUE_CATEGORIES:
        for stored_memory in memory["memories"]:
            if not isinstance(stored_memory, dict):
                continue

            stored_key = str(stored_memory.get("key", "")).strip().lower()
            stored_value = str(stored_memory.get("value", "")).strip().lower()
            stored_category = str(stored_memory.get("category", "")).strip().lower()

            if (
                stored_key == key.lower()
                and stored_value == value.lower()
                and stored_category == category
            ):
                return

        memory["memories"].append(new_memory)
        save_memory(memory)
        return

    for stored_memory in memory["memories"]:
        if not isinstance(stored_memory, dict):
            continue

        stored_key = str(stored_memory.get("key", "")).strip().lower()
        stored_category = str(stored_memory.get("category", "")).strip().lower()

        if stored_key == key.lower() and stored_category == category:
            stored_memory.update(new_memory)
            save_memory(memory)
            return

    memory["memories"].append(new_memory)
    save_memory(memory)


def recall(key):
    """Retrieve the first memory matching a key."""
    key = str(key).strip().lower()
    memory = load_memory()

    for stored_memory in memory["memories"]:
        if not isinstance(stored_memory, dict):
            continue

        stored_key = str(stored_memory.get("key", "")).strip().lower()
        if stored_key == key:
            return stored_memory.get("value")

    return None


def recall_all(key):
    """Retrieve all memories matching a key."""
    key = str(key).strip().lower()
    memory = load_memory()
    results = []

    for stored_memory in memory["memories"]:
        if not isinstance(stored_memory, dict):
            continue

        stored_key = str(stored_memory.get("key", "")).strip().lower()
        if stored_key == key:
            results.append(stored_memory)

    return results


def get_by_category(category):
    """Retrieve every memory belonging to a category."""
    category = str(category).strip().lower()
    memory = load_memory()
    results = []

    for stored_memory in memory["memories"]:
        if not isinstance(stored_memory, dict):
            continue

        stored_category = str(stored_memory.get("category", "")).strip().lower()
        if stored_category == category:
            results.append(stored_memory)

    return results


def get_all_memories():
    """Return every valid stored memory."""
    memory = load_memory()
    return [
        stored_memory
        for stored_memory in memory["memories"]
        if isinstance(stored_memory, dict)
    ]
