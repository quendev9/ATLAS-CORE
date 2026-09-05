def classify_input(user_input):
    """Perform coarse classification of a user request."""
    if not isinstance(user_input, str):
        return "EMPTY"

    text = user_input.strip()
    if not text:
        return "EMPTY"

    lowered = text.lower()

    if lowered.startswith("remember ") or lowered.startswith("recall "):
        return "MEMORY_COMMAND"

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
