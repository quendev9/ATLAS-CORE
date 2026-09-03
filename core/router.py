def classify_input(user_input):
    """
    Classify a user input into a request type.

    The router performs coarse classification.
    The memory manager performs detailed
    memory detection.
    """

    text = user_input.strip()

    lowered = text.lower()

    if not text:
        return "EMPTY"

    # -----------------------------------
    # MEMORY COMMAND
    # -----------------------------------

    if lowered.startswith("remember "):

        return "MEMORY_COMMAND"

    if lowered.startswith("recall "):

        return "MEMORY_COMMAND"

    # -----------------------------------
    # MEMORY QUERY
    # -----------------------------------

    memory_queries = [

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

        "what are my aspirations"
    ]

    if lowered.rstrip("?") in memory_queries:

        return "MEMORY_QUERY"

    if (
        lowered.startswith(
            "what is my favorite "
        )
        or lowered.startswith(
            "what's my favorite "
        )
    ):

        return "MEMORY_QUERY"

    # -----------------------------------
    # MEMORY STATEMENT
    # -----------------------------------

    memory_statements = [

        "my favorite ",
        "my name is ",

        "i live in ",

        "i like ",
        "i love ",
        "i hate ",
        "i prefer ",
        "i enjoy ",

        "i'm interested in ",
        "im interested in ",
        "i am interested in ",

        "my project is ",

        "i'm working on ",
        "im working on ",
        "i am working on ",

        "my goal is ",
        "i want to ",

        "i hope to ",
        "i hope i can ",
        "i dream of ",

        "i'm ",
        "im ",
        "i am "
    ]

    for prefix in memory_statements:

        if lowered.startswith(prefix):

            return "MEMORY_STATEMENT"

    # -----------------------------------
    # DEFAULT
    # -----------------------------------

    return "AI_REQUEST"