from memory.memory import remember, recall, get_all_memories


# -----------------------------------
# IMPORTANCE
# -----------------------------------

def get_importance(category):
    """
    Assign an importance score based on memory category.
    """

    importance_scores = {
        "identity": 1.0,
        "location": 0.9,
        "project": 0.9,
        "preference": 0.8,
        "other": 0.5
    }

    return importance_scores.get(category, 0.5)


# -----------------------------------
# HIGH-LEVEL MEMORY OPERATIONS
# -----------------------------------

def remember_memory(
    key,
    value,
    category="other",
    importance=None
):
    """
    High-level function for storing a memory.

    The manager decides the importance if one
    is not provided.
    """

    if importance is None:
        importance = get_importance(category)

    remember(
        key,
        value,
        category,
        importance
    )

    return {
        "key": key,
        "value": value,
        "category": category,
        "importance": importance
    }


def recall_memory(key):
    """
    High-level function for retrieving a memory.
    """

    return recall(key)


def get_memories():
    """
    High-level function for retrieving all memories.
    """

    return get_all_memories()


# -----------------------------------
# MEMORY DETECTION
# -----------------------------------

def detect_memory(user_input):
    """
    Detect and extract user-relevant information.

    Returns:
        (key, value, category)

    or:

        None
    """

    text = user_input.strip()

    if not text:
        return None

    lowered = text.lower()

    # -----------------------------------
    # PROJECT
    # -----------------------------------

    if lowered.startswith("my project is "):

        value = text[len("my project is "):].strip()

        return "my project", value, "project"

    if lowered.startswith("i'm working on "):

        value = text[len("i'm working on "):].strip()

        return "current project", value, "project"

    if lowered.startswith("im working on "):

        value = text[len("im working on "):].strip()

        return "current project", value, "project"

    if lowered.startswith("i am working on "):

        value = text[len("i am working on "):].strip()

        return "current project", value, "project"

    # -----------------------------------
    # LOCATION
    # -----------------------------------

    if lowered.startswith("i live in "):

        value = text[len("i live in "):].strip()

        return "location", value, "location"

    # -----------------------------------
    # IDENTITY
    # -----------------------------------

    if lowered.startswith("my name is "):

        value = text[len("my name is "):].strip()

        return "name", value, "identity"

    if lowered.startswith("i am "):

        value = text[len("i am "):].strip()

        return "identity", value, "identity"

    if lowered.startswith("i'm "):

        value = text[len("i'm "):].strip()

        return "identity", value, "identity"

    if lowered.startswith("im "):

        value = text[len("im "):].strip()

        return "identity", value, "identity"

    # -----------------------------------
    # PREFERENCES
    # -----------------------------------

    if lowered.startswith("my favorite "):

        remainder = text[len("my favorite "):].strip()

        if " is " in remainder.lower():

            index = remainder.lower().find(" is ")

            subject = remainder[:index].strip()
            value = remainder[index + 4:].strip()

            return (
                f"favorite {subject}",
                value,
                "preference"
            )

    if lowered.startswith("i like "):

        value = text[len("i like "):].strip()

        return "likes", value, "preference"

    if lowered.startswith("i love "):

        value = text[len("i love "):].strip()

        return "loves", value, "preference"

    if lowered.startswith("i hate "):

        value = text[len("i hate "):].strip()

        return "dislikes", value, "preference"

    if lowered.startswith("i prefer "):

        value = text[len("i prefer "):].strip()

        return "preferences", value, "preference"

    if lowered.startswith("i enjoy "):

        value = text[len("i enjoy "):].strip()

        return "enjoys", value, "preference"

    return None


# -----------------------------------
# AUTOMATIC MEMORY PROCESSING
# -----------------------------------

def process_memory(user_input):
    """
    Detect, classify, assign importance,
    and save a memory.

    Returns:
        A memory dictionary if detected.

    Otherwise:
        None
    """

    result = detect_memory(user_input)

    if result is None:
        return None

    key, value, category = result

    return remember_memory(
        key,
        value,
        category
    )


# -----------------------------------
# TESTING
# -----------------------------------

if __name__ == "__main__":

    print("MEMORY MANAGER TEST")
    print("-------------------")

    test_inputs = [
        "My favorite color is blue",
        "My name is Quen",
        "I live in New York City",
        "My project is ATLAS",
        "I like robotics",
        "I love building robots",
        "I am an engineering student",
        "I'm working on ATLAS",
        "The sky is blue"
    ]

    for user_input in test_inputs:

        print(f"\nInput: {user_input}")

        result = process_memory(user_input)

        if result:

            print(
                f"[MEMORY] Saved "
                f"({result['category']}, "
                f"importance={result['importance']}): "
                f"{result['key']} → "
                f"{result['value']}"
            )

        else:

            print("No memory detected.")