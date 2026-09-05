from memory.memory import (
    remember,
    recall,
    get_by_category,
    get_all_memories,
)


IMPORTANCE_SCORES = {
    "identity": 1.0,
    "location": 0.9,
    "project": 0.9,
    "goal": 0.9,
    "aspiration": 0.9,
    "preference": 0.8,
    "interest": 0.8,
    "likes": 0.8,
    "loves": 0.8,
    "dislikes": 0.8,
    "enjoys": 0.8,
    "other": 0.5,
}


def get_importance(category):
    """Assign an importance score based on memory category."""
    return IMPORTANCE_SCORES.get(category, 0.5)


def remember_memory(key, value, category="other", importance=None):
    """High-level interface for storing a memory."""
    key = str(key).strip()
    value = str(value).strip()
    category = str(category).strip().lower()

    if not key or not value:
        return None

    if importance is None:
        importance = get_importance(category)

    remember(key, value, category, importance)

    return {
        "key": key,
        "value": value,
        "category": category,
        "importance": importance,
    }


def normalize_memory_key(key):
    key = str(key).strip()
    if key.lower().startswith("my "):
        key = key[3:].strip()
    return key


def recall_memory(key):
    return recall(normalize_memory_key(key))


def get_memories():
    return get_all_memories()


def get_memories_by_category(category):
    return get_by_category(str(category).strip().lower())


def extract_after_prefix(text, prefix):
    value = text[len(prefix):].strip()
    return value if value else None


def clean_memory_value(value):
    if not value:
        return None

    value = value.strip().rstrip(".,!? ")
    return value if value else None


def detect_memory(user_input):
    """Detect durable, user-relevant information worth storing."""
    if not isinstance(user_input, str):
        return None

    text = user_input.strip()
    if not text:
        return None

    lowered = text.lower()

    project_prefixes = (
        "my project is ",
        "i'm working on ",
        "im working on ",
        "i am working on ",
    )
    for prefix in project_prefixes:
        if lowered.startswith(prefix):
            value = clean_memory_value(extract_after_prefix(text, prefix))
            if value:
                return ("projects", value, "project")

    if lowered.startswith("i live in "):
        value = clean_memory_value(extract_after_prefix(text, "i live in "))
        if value:
            return ("location", value, "location")

    interest_prefixes = (
        "i'm interested in ",
        "im interested in ",
        "i am interested in ",
        "i'm really into ",
        "im really into ",
        "i am really into ",
        "i'm into ",
        "im into ",
        "i am into ",
    )
    for prefix in interest_prefixes:
        if lowered.startswith(prefix):
            value = clean_memory_value(extract_after_prefix(text, prefix))
            if value:
                return ("interests", value, "interest")

    goal_prefixes = (
        "my goal is ",
        "i want to ",
    )
    for prefix in goal_prefixes:
        if lowered.startswith(prefix):
            value = clean_memory_value(extract_after_prefix(text, prefix))
            if value:
                return ("goals", value, "goal")

    aspiration_prefixes = (
        "i hope to ",
        "i hope i can ",
        "i dream of ",
    )
    for prefix in aspiration_prefixes:
        if lowered.startswith(prefix):
            value = clean_memory_value(extract_after_prefix(text, prefix))
            if value:
                return ("aspirations", value, "aspiration")

    if lowered.startswith("my name is "):
        value = clean_memory_value(extract_after_prefix(text, "my name is "))
        if value:
            return ("name", value, "identity")

    if lowered.startswith("my favorite "):
        remainder = text[len("my favorite "):].strip()
        remainder_lower = remainder.lower()

        if " is " in remainder_lower:
            index = remainder_lower.find(" is ")
            subject = clean_memory_value(remainder[:index])
            value = clean_memory_value(remainder[index + 4:])

            if subject and value:
                return (f"favorite {subject}", value, "preference")

    marker = " is my favorite "
    if marker in lowered:
        index = lowered.find(marker)
        value = clean_memory_value(text[:index])
        subject = clean_memory_value(text[index + len(marker):])

        if value and subject:
            return (f"favorite {subject}", value, "preference")

    like_prefixes = ("i like ", "i really like ")
    for prefix in like_prefixes:
        if lowered.startswith(prefix):
            value = clean_memory_value(extract_after_prefix(text, prefix))
            if value:
                return ("likes", value, "likes")

    love_prefixes = ("i love ", "i really love ")
    for prefix in love_prefixes:
        if lowered.startswith(prefix):
            value = clean_memory_value(extract_after_prefix(text, prefix))
            if value:
                return ("loves", value, "loves")

    if lowered.startswith("i hate "):
        value = clean_memory_value(extract_after_prefix(text, "i hate "))
        if value:
            return ("dislikes", value, "dislikes")

    if lowered.startswith("i prefer "):
        value = clean_memory_value(extract_after_prefix(text, "i prefer "))
        if value:
            return ("preferences", value, "preference")

    if lowered.startswith("i enjoy "):
        value = clean_memory_value(extract_after_prefix(text, "i enjoy "))
        if value:
            return ("enjoys", value, "enjoys")

    return None


def process_memory(user_input):
    result = detect_memory(user_input)
    if result is None:
        return None

    key, value, category = result
    return remember_memory(key, value, category)


def query_memory(user_input):
    """Answer supported memory queries without calling the AI model."""
    if not isinstance(user_input, str):
        return None

    text = user_input.strip()
    lowered = text.lower()
    normalized = lowered.rstrip("?").strip()

    if normalized == "what are my favorites":
        memories = get_memories_by_category("preference")
        responses = []

        for memory in memories:
            key = memory.get("key", "")
            value = memory.get("value", "")
            if key.startswith("favorite "):
                subject = key[len("favorite "):]
                responses.append(f"Your favorite {subject} is {value}.")

        return " ".join(responses) if responses else "I don't have any favorites stored in my memory."

    if normalized in ("what do i like", "what do you know i like"):
        categories = {"preference", "likes", "loves", "dislikes", "enjoys"}
        memories = [m for m in get_memories() if m.get("category") in categories]
        responses = []

        for memory in memories:
            key = memory.get("key", "")
            value = memory.get("value", "")
            if key == "likes":
                responses.append(f"You like {value}.")
            elif key == "loves":
                responses.append(f"You love {value}.")
            elif key == "dislikes":
                responses.append(f"You dislike {value}.")
            elif key == "enjoys":
                responses.append(f"You enjoy {value}.")
            elif key.startswith("favorite "):
                subject = key[len("favorite "):]
                responses.append(f"Your favorite {subject} is {value}.")

        return " ".join(responses) if responses else "I don't have any preferences about you in my memory."

    if normalized.startswith("what is my favorite "):
        subject = text[len("what is my favorite "):].rstrip("?").strip()
        if not subject:
            return None
        value = recall_memory(f"favorite {subject}")
        return f"Your favorite {subject} is {value}." if value is not None else f"I don't have your favorite {subject} in my memory."

    if normalized.startswith("what's my favorite "):
        subject = text[len("what's my favorite "):].rstrip("?").strip()
        if not subject:
            return None
        value = recall_memory(f"favorite {subject}")
        return f"Your favorite {subject} is {value}." if value is not None else f"I don't have your favorite {subject} in my memory."

    if normalized in ("what is my name", "what's my name"):
        value = recall_memory("name")
        return f"Your name is {value}." if value is not None else "I don't have your name in my memory."

    if normalized == "where do i live":
        value = recall_memory("location")
        return f"You live in {value}." if value is not None else "I don't have your location in my memory."

    if normalized in ("what project am i working on", "what am i working on", "what projects am i working on", "what projects do i have"):
        projects = get_memories_by_category("project")
        values = [project.get("value", "") for project in projects]
        return "Your projects include: " + ", ".join(values) + "." if values else "I don't have any projects stored in my memory."

    if normalized in ("what am i interested in", "what are my interests"):
        interests = get_memories_by_category("interest")
        values = [interest.get("value", "") for interest in interests]
        return "You're interested in: " + ", ".join(values) + "." if values else "I don't have any interests about you in my memory."

    if normalized in ("what are my goals", "what are my goals in life"):
        goals = get_memories_by_category("goal")
        values = [goal.get("value", "") for goal in goals]
        return "Your goals include: " + ", ".join(values) + "." if values else "I don't have any goals stored in my memory."

    if normalized == "what are my aspirations":
        aspirations = get_memories_by_category("aspiration")
        values = [aspiration.get("value", "") for aspiration in aspirations]
        return "Your aspirations include: " + ", ".join(values) + "." if values else "I don't have any aspirations stored in my memory."

    if normalized == "what do you remember about me":
        memories = get_memories()
        if not memories:
            return "I don't have anything stored about you yet."
        lines = [f"- {m.get('key', 'unknown')}: {m.get('value', '')}" for m in memories]
        return "Here's what I remember about you:\n" + "\n".join(lines)

    return None
