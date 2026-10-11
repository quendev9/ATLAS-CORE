"""
ATLAS Memory Intelligence

Evaluates user messages and extracts potentially useful
long-term information.
"""

from memory.manager import extract_facts


TEMPORARY_SIGNALS = (
    "today",
    "right now",
    "currently",
    "this morning",
    "tonight",
    "yesterday",
    "tomorrow",
    "for now",
)


DURABLE_SIGNALS = (
    "i've been",
    "i have been",
    "i'm learning",
    "im learning",
    "i am learning",
    "i'm building",
    "im building",
    "i am building",
    "i'm studying",
    "im studying",
    "i am studying",
    "i'm interested",
    "im interested",
    "i am interested",
    "i want to",
    "i hope to",
    "i plan to",
    "i'm working on",
    "im working on",
    "i am working on",
    "i prefer",
    "i enjoy",
    "i like",
    "i love",
)


def clean_value(value):
    """Clean extracted memory text."""

    if not value:
        return None

    value = value.strip()
    value = value.rstrip(".,!? ")

    return value if value else None


def extract_memory(user_input):
    """
    Try to extract a simple memory from a user statement.

    Returns:
        dict containing category, key, and value.
        None if nothing useful can be extracted.
    """
    facts = extract_facts(user_input)
    if not facts:
        return None
    fact = facts[0]
    return {
        "category": fact.get("category", "other"),
        "key": fact.get("key", ""),
        "value": fact.get("value", ""),
    }


def evaluate_memory(user_input):
    """
    Evaluate a message and determine whether it contains
    potentially durable information.

    Returns a structured evaluation dictionary.
    """

    if not isinstance(user_input, str):
        return None

    text = user_input.strip()

    if not text:
        return None

    lowered = text.lower()

    score = 0
    reasons = []

    # Temporary information reduces confidence.
    for signal in TEMPORARY_SIGNALS:
        if signal in lowered:
            score -= 1
            reasons.append(f"temporary signal: {signal}")

    # Durable information increases confidence.
    for signal in DURABLE_SIGNALS:
        if signal in lowered:
            score += 2
            reasons.append(f"durable signal: {signal}")

    # First-person statements are more likely to contain
    # information about the user.
    if lowered.startswith(("i ", "i'm ", "im ", "i am ")):
        score += 1
        reasons.append("first-person statement")

    # Longer statements are more likely to contain useful context.
    if len(text.split()) >= 4:
        score += 1
        reasons.append("substantial statement")

    worth_remembering = score >= 2

    memory = None

    if worth_remembering:
        memory = extract_memory(text)

    return {
        "worth_remembering": worth_remembering,
        "score": score,
        "reasons": reasons,
        "memory": memory,
        "text": text,
    }