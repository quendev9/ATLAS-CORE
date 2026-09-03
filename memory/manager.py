from memory.memory import (
    remember,
    recall,
    recall_all,
    get_by_category,
    get_all_memories
)


# -----------------------------------
# IMPORTANCE
# -----------------------------------

def get_importance(category):
    """
    Assign an importance score based
    on the memory category.
    """

    importance_scores = {

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

        "other": 0.5
    }

    return importance_scores.get(
        category,
        0.5
    )


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
    High-level interface for storing memory.
    """

    if importance is None:
        importance = get_importance(
            category
        )

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
    Retrieve a single memory value.
    """

    key = normalize_memory_key(key)

    return recall(key)


def get_memories():
    """
    Retrieve every stored memory.
    """

    return get_all_memories()


def get_memories_by_category(category):
    """
    Retrieve memories belonging to a category.
    """

    return get_by_category(category)


# -----------------------------------
# MEMORY DETECTION
# -----------------------------------

def detect_memory(user_input):
    """
    Detect and classify user-relevant information.

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

        if value:
            return (
                "projects",
                value,
                "project"
            )

    if lowered.startswith("i'm working on "):

        value = text[len("i'm working on "):].strip()

        if value:
            return (
                "projects",
                value,
                "project"
            )

    if lowered.startswith("im working on "):

        value = text[len("im working on "):].strip()

        if value:
            return (
                "projects",
                value,
                "project"
            )

    if lowered.startswith("i am working on "):

        value = text[len("i am working on "):].strip()

        if value:
            return (
                "projects",
                value,
                "project"
            )

    # -----------------------------------
    # LOCATION
    # -----------------------------------

    if lowered.startswith("i live in "):

        value = text[len("i live in "):].strip()

        if value:
            return (
                "location",
                value,
                "location"
            )

    # -----------------------------------
    # INTEREST
    # -----------------------------------

    if lowered.startswith("i'm interested in "):

        value = text[
            len("i'm interested in "):
        ].strip()

        if value:
            return (
                "interests",
                value,
                "interest"
            )

    if lowered.startswith("im interested in "):

        value = text[
            len("im interested in "):
        ].strip()

        if value:
            return (
                "interests",
                value,
                "interest"
            )

    if lowered.startswith("i am interested in "):

        value = text[
            len("i am interested in "):
        ].strip()

        if value:
            return (
                "interests",
                value,
                "interest"
            )

    # -----------------------------------
    # GOALS
    # -----------------------------------

    if lowered.startswith("my goal is "):

        value = text[len("my goal is "):].strip()

        if value:
            return (
                "goals",
                value,
                "goal"
            )

    if lowered.startswith("my goal is to "):

        value = text[len("my goal is to "):].strip()

        if value:
            return (
                "goals",
                value,
                "goal"
            )

    if lowered.startswith("i want to "):

        value = text[len("i want to "):].strip()

        if value:
            return (
                "goals",
                value,
                "goal"
            )

    # -----------------------------------
    # ASPIRATIONS
    # -----------------------------------

    if lowered.startswith("i hope to "):

        value = text[len("i hope to "):].strip()

        if value:
            return (
                "aspirations",
                value,
                "aspiration"
            )

    if lowered.startswith("i hope i can "):

        value = text[len("i hope i can "):].strip()

        if value:
            return (
                "aspirations",
                value,
                "aspiration"
            )

    if lowered.startswith("i dream of "):

        value = text[len("i dream of "):].strip()

        if value:
            return (
                "aspirations",
                value,
                "aspiration"
            )

    # -----------------------------------
    # IDENTITY
    # -----------------------------------

    if lowered.startswith("my name is "):

        value = text[len("my name is "):].strip()

        if value:
            return (
                "name",
                value,
                "identity"
            )

    # -----------------------------------
    # FAVORITE / PREFERENCES
    # -----------------------------------

    if lowered.startswith("my favorite "):

        remainder = text[
            len("my favorite "):
        ].strip()

        if " is " in remainder.lower():

            index = remainder.lower().find(
                " is "
            )

            subject = remainder[:index].strip()

            value = remainder[
                index + 4:
            ].strip()

            if subject and value:

                return (
                    f"favorite {subject}",
                    value,
                    "preference"
                )

    # -----------------------------------
    # LIKES
    # -----------------------------------

    if lowered.startswith("i like "):

        value = text[len("i like "):].strip()

        if value:
            return (
                "likes",
                value,
                "likes"
            )

    # -----------------------------------
    # LOVES
    # -----------------------------------

    if lowered.startswith("i love "):

        value = text[len("i love "):].strip()

        if value:
            return (
                "loves",
                value,
                "loves"
            )

    # -----------------------------------
    # DISLIKES
    # -----------------------------------

    if lowered.startswith("i hate "):

        value = text[len("i hate "):].strip()

        if value:
            return (
                "dislikes",
                value,
                "dislikes"
            )

    # -----------------------------------
    # PREFERENCES
    # -----------------------------------

    if lowered.startswith("i prefer "):

        value = text[len("i prefer "):].strip()

        if value:
            return (
                "preferences",
                value,
                "preference"
            )

    # -----------------------------------
    # ENJOYS
    # -----------------------------------

    if lowered.startswith("i enjoy "):

        value = text[len("i enjoy "):].strip()

        if value:
            return (
                "enjoys",
                value,
                "enjoys"
            )

    # -----------------------------------
    # GENERAL IDENTITY
    # -----------------------------------

    if lowered.startswith("i am "):

        value = text[len("i am "):].strip()

        if value:
            return (
                "identity",
                value,
                "identity"
            )

    if lowered.startswith("i'm "):

        value = text[len("i'm "):].strip()

        if value:
            return (
                "identity",
                value,
                "identity"
            )

    if lowered.startswith("im "):

        value = text[len("im "):].strip()

        if value:
            return (
                "identity",
                value,
                "identity"
            )

    return None


# -----------------------------------
# AUTOMATIC MEMORY PROCESSING
# -----------------------------------

def process_memory(user_input):
    """
    Detect, classify, assign importance,
    and save a memory.
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
# NORMALIZATION
# -----------------------------------

def normalize_memory_key(key):
    """
    Normalize a memory key before retrieval.
    """

    key = key.strip()

    if key.lower().startswith("my "):

        key = key[3:].strip()

    return key


# -----------------------------------
# MEMORY QUERIES
# -----------------------------------

def query_memory(user_input):
    """
    Answer natural-language questions using
    local memory only.
    """

    text = user_input.strip()

    lowered = text.lower()

    # -----------------------------------
    # FAVORITES
    # -----------------------------------

    if lowered in [
        "what are my favorites",
        "what are my favorites?"
    ]:

        memories = get_memories_by_category(
            "preference"
        )

        if not memories:

            return (
                "I don't have any favorites "
                "stored in my memory."
            )

        responses = []

        for memory in memories:

            key = memory["key"]

            value = memory["value"]

            if key.startswith("favorite "):

                subject = key[
                    len("favorite "):
                ]

                responses.append(
                    f"Your favorite "
                    f"{subject} is {value}."
                )

        if not responses:

            return (
                "I don't have any favorites "
                "stored in my memory."
            )

        return " ".join(responses)

    # -----------------------------------
    # WHAT DO I LIKE?
    # -----------------------------------

    if lowered in [
        "what do i like",
        "what do i like?",
        "what do you know i like",
        "what do you know i like?"
    ]:

        categories = [
            "preference",
            "likes",
            "loves",
            "dislikes",
            "enjoys"
        ]

        memories = [
            memory
            for memory in get_memories()
            if memory["category"]
            in categories
        ]

        if not memories:

            return (
                "I don't have any preferences "
                "about you in my memory."
            )

        responses = []

        for memory in memories:

            key = memory["key"]

            value = memory["value"]

            if key == "likes":

                responses.append(
                    f"You like {value}."
                )

            elif key == "loves":

                responses.append(
                    f"You love {value}."
                )

            elif key == "dislikes":

                responses.append(
                    f"You dislike {value}."
                )

            elif key == "enjoys":

                responses.append(
                    f"You enjoy {value}."
                )

            elif key.startswith("favorite "):

                subject = key[
                    len("favorite "):
                ]

                responses.append(
                    f"Your favorite "
                    f"{subject} is {value}."
                )

        return " ".join(responses)

    # -----------------------------------
    # FAVORITE X
    # -----------------------------------

    if (
        lowered.startswith(
            "what is my favorite "
        )
        or lowered.startswith(
            "what's my favorite "
        )
    ):

        if lowered.startswith(
            "what is my favorite "
        ):

            subject = text[
                len("what is my favorite "):
            ].strip()

        else:

            subject = text[
                len("what's my favorite "):
            ].strip()

        subject = subject.rstrip(
            "?"
        ).strip()

        if not subject:
            return None

        value = recall_memory(
            f"favorite {subject}"
        )

        if value is None:

            return (
                f"I don't have your favorite "
                f"{subject} in my memory."
            )

        return (
            f"Your favorite {subject} "
            f"is {value}."
        )

    # -----------------------------------
    # NAME
    # -----------------------------------

    if lowered in [
        "what is my name",
        "what is my name?",
        "what's my name",
        "what's my name?"
    ]:

        value = recall_memory("name")

        if value is None:

            return (
                "I don't have your name "
                "in my memory."
            )

        return f"Your name is {value}."

    # -----------------------------------
    # LOCATION
    # -----------------------------------

    if lowered in [
        "where do i live",
        "where do i live?"
    ]:

        value = recall_memory("location")

        if value is None:

            return (
                "I don't have your location "
                "in my memory."
            )

        return f"You live in {value}."

    # -----------------------------------
    # PROJECTS
    # -----------------------------------

    if lowered in [
        "what projects am i working on",
        "what projects am i working on?",
        "what projects do i have",
        "what projects do i have?"
    ]:

        projects = get_memories_by_category(
            "project"
        )

        if not projects:

            return (
                "I don't have any projects "
                "stored in my memory."
            )

        values = [
            project["value"]
            for project in projects
        ]

        return (
            "Your projects include: "
            + ", ".join(values)
            + "."
        )

    # -----------------------------------
    # INTERESTS
    # -----------------------------------

    if lowered in [
        "what am i interested in",
        "what am i interested in?",
        "what are my interests",
        "what are my interests?"
    ]:

        interests = get_memories_by_category(
            "interest"
        )

        if not interests:

            return (
                "I don't have any interests "
                "about you in my memory."
            )

        values = [
            interest["value"]
            for interest in interests
        ]

        return (
            "You're interested in: "
            + ", ".join(values)
            + "."
        )

    # -----------------------------------
    # GOALS
    # -----------------------------------

    if lowered in [
        "what are my goals",
        "what are my goals?",
        "what are my goals in life",
        "what are my goals in life?"
    ]:

        goals = get_memories_by_category(
            "goal"
        )

        if not goals:

            return (
                "I don't have any goals "
                "stored in my memory."
            )

        values = [
            goal["value"]
            for goal in goals
        ]

        return (
            "Your goals include: "
            + ", ".join(values)
            + "."
        )

    # -----------------------------------
    # ASPIRATIONS
    # -----------------------------------

    if lowered in [
        "what are my aspirations",
        "what are my aspirations?"
    ]:

        aspirations = get_memories_by_category(
            "aspiration"
        )

        if not aspirations:

            return (
                "I don't have any aspirations "
                "stored in my memory."
            )

        values = [
            aspiration["value"]
            for aspiration in aspirations
        ]

        return (
            "Your aspirations include: "
            + ", ".join(values)
            + "."
        )

    # -----------------------------------
    # EVERYTHING
    # -----------------------------------

    if lowered in [
        "what do you remember about me",
        "what do you remember about me?"
    ]:

        memories = get_memories()

        if not memories:

            return (
                "I don't have anything stored "
                "about you yet."
            )

        responses = []

        for memory in memories:

            responses.append(
                f"- {memory['key']}: "
                f"{memory['value']}"
            )

        return (
            "Here's what I remember about you:\n"
            + "\n".join(responses)
        )

    return None