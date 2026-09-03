import json
from pathlib import Path


MEMORY_FILE = Path(__file__).parent / "memory.json"


# Categories that can contain multiple memories.
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
    """
    Load all stored memories from disk.

    If the memory file does not exist, return
    an empty memory structure.
    """

    if not MEMORY_FILE.exists():
        return {"memories": []}

    try:
        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            memory = json.load(file)

    except (
        json.JSONDecodeError,
        OSError
    ):
        return {"memories": []}

    if "memories" not in memory:
        memory["memories"] = []

    return memory


def save_memory(memory):
    """
    Save the complete memory structure to disk.
    """

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            memory,
            file,
            indent=4,
            ensure_ascii=False
        )


def remember(
    key,
    value,
    category="other",
    importance=0.5
):
    """
    Store a memory.

    Single-value categories:
        Existing memory is updated.

    Multi-value categories:
        Multiple unique memories can coexist.
    """

    memory = load_memory()

    new_memory = {
        "key": key,
        "value": value,
        "category": category,
        "importance": importance
    }

    # -----------------------------------
    # MULTI-VALUE MEMORY
    # -----------------------------------

    if category in MULTI_VALUE_CATEGORIES:

        for stored_memory in memory["memories"]:

            same_key = (
                stored_memory["key"].lower()
                == key.lower()
            )

            same_value = (
                stored_memory["value"].lower()
                == value.lower()
            )

            same_category = (
                stored_memory["category"].lower()
                == category.lower()
            )

            if (
                same_key
                and same_value
                and same_category
            ):
                return

        memory["memories"].append(new_memory)

        save_memory(memory)

        return

    # -----------------------------------
    # SINGLE-VALUE MEMORY
    # -----------------------------------

    for stored_memory in memory["memories"]:

        same_key = (
            stored_memory["key"].lower()
            == key.lower()
        )

        same_category = (
            stored_memory["category"].lower()
            == category.lower()
        )

        if same_key and same_category:

            stored_memory.update(new_memory)

            save_memory(memory)

            return

    # -----------------------------------
    # NEW MEMORY
    # -----------------------------------

    memory["memories"].append(new_memory)

    save_memory(memory)


def recall(key):
    """
    Retrieve the first memory matching a key.

    Returns:
        Stored value
        or None
    """

    memory = load_memory()

    for stored_memory in memory["memories"]:

        if (
            stored_memory["key"].lower()
            == key.lower()
        ):

            return stored_memory["value"]

    return None


def recall_all(key):
    """
    Retrieve all memories matching a key.

    Useful for multi-value memories such as:
        likes
        interests
        projects
        goals
        aspirations
    """

    memory = load_memory()

    results = []

    for stored_memory in memory["memories"]:

        if (
            stored_memory["key"].lower()
            == key.lower()
        ):

            results.append(stored_memory)

    return results


def get_by_category(category):
    """
    Retrieve every memory belonging to a category.
    """

    memory = load_memory()

    return [
        stored_memory
        for stored_memory in memory["memories"]
        if stored_memory["category"].lower()
        == category.lower()
    ]


def get_all_memories():
    """
    Return every stored memory.
    """

    memory = load_memory()

    return memory["memories"]