import re

from memory.manager import extract_facts, is_project_decision_query


def classify_input(user_input):
    """Perform coarse classification of a user request."""
    if not isinstance(user_input, str):
        return "EMPTY"

    text = user_input.strip()
    if not text:
        return "EMPTY"

    lowered = text.lower()
    normalized = lowered.rstrip("?").strip()

    if lowered.startswith("remember ") or lowered.startswith("recall "):
        return "MEMORY_COMMAND"

    if is_project_decision_query(text):
        return "MEMORY_QUERY"

    if lowered.startswith(
        (
            "what do you remember about ",
            "what do you know about ",
            "what did i tell you about ",
        )
    ):
        return "MEMORY_QUERY"

    if re.match(
        r"^(?:do\s+you\s+(?:remember|still\s+remember|know))\s+"
        r"(?:my\s+|the\s+|your\s+)?[A-Za-z0-9][A-Za-z0-9 _-]*\??$",
        normalized,
        re.IGNORECASE,
    ):
        return "MEMORY_QUERY"

    if re.match(
        r"^(?:what(?:'s|\s+is)\s+(?:my\s+|the\s+|your\s+)?"
        r"[A-Za-z0-9][A-Za-z0-9 _-]*\s+(?:named|called))\??$",
        normalized,
        re.IGNORECASE,
    ) or re.match(
        r"^(?:what(?:'s|\s+is)\s+the\s+name\s+of\s+)"
        r"(?:my\s+|the\s+|your\s+)?[A-Za-z0-9][A-Za-z0-9 _-]*\??$",
        normalized,
        re.IGNORECASE,
    ):
        return "MEMORY_QUERY"

    if re.match(
        r"^(?:what(?:'s|\s+is)\s+)(?:my\s+|the\s+|your\s+)"
        r"[A-Za-z0-9][A-Za-z0-9 _'-]*['’]s\s+name\??$",
        normalized,
        re.IGNORECASE,
    ):
        return "MEMORY_QUERY"

    if extract_facts(text):
        return "MEMORY_CANDIDATE"

    memory_queries = (
        "what do i like",
        "what do you know i like",
        "what are my favorites",
        "what do you remember about me",
        "what am i interested in",
        "what are my interests",
        "what is my name",
        "what's my name",
        "where do i live",
        "what project am i working on",
        "what am i working on",
        "what projects am i working on",
        "what projects do i have",
        "what are my latest projects",
        "what are my most recent projects",
        "what are my two latest projects",
        "what are my two most recent projects",
        "what are my goals",
        "what are my goals in life",
        "what are my aspirations",
    )

    normalized_query = lowered.rstrip("?").strip()

    if normalized_query in memory_queries:
        return "MEMORY_QUERY"

    if (
        normalized_query.startswith("what is my favorite ")
        or normalized_query.startswith("what's my favorite ")
    ):
        return "MEMORY_QUERY"

    if normalized_query.startswith("what is ") or normalized_query.startswith("what's "):
        entity = normalized_query[8:].strip() if normalized_query.startswith("what is ") else normalized_query[8:].strip()
        if entity and " related to " not in entity:
            from memory.manager import get_memories
            from memory.project_memory import get_project_facts
            for memory in get_memories():
                subject = str(memory.get("subject", "")).lower()
                value = str(memory.get("value", "")).lower()
                if entity in subject or entity in value or subject in entity or value in entity:
                    return "MEMORY_QUERY"
            for fact in get_project_facts():
                if entity == str(fact.get("subject", "")).strip().lower():
                    return "MEMORY_QUERY"

    memory_prefixes = (
        "my name is ",
        "my favorite ",
        "my project is ",
        "i live in ",
        "i'm interested in ",
        "im interested in ",
        "i am interested in ",
        "i'm working on ",
        "im working on ",
        "i am working on ",
        "my goal is ",
        "i want to ",
        "i hope to ",
        "i hope i can ",
        "i dream of ",
        "i like ",
        "i love ",
        "i hate ",
        "i prefer ",
        "i enjoy ",
        "i'm really into ",
        "im really into ",
        "i am really into ",
        "i'm into ",
        "im into ",
        "i am into ",
        "i really like ",
        "i really love ",
    )

    if lowered.startswith(memory_prefixes):
        return "MEMORY_CANDIDATE"

    if " is my favorite " in lowered:
        return "MEMORY_CANDIDATE"

    return "AI_REQUEST"
