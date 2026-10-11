
import re
import math
import uuid
from datetime import datetime, timezone

from memory.memory import (
    remember,
    recall,
    get_by_category,
    get_all_memories,
    load_memory,
    save_memory,
    MULTI_VALUE_CATEGORIES,
    MEMORY_STATUSES,
)
from memory.project_memory import get_project_facts, remember_project_fact


IMPORTANCE_SCORES = {
    "identity": 1.0,
    "location": 0.9,
    "project": 0.9,
    "goal": 0.9,
    "aspiration": 0.9,
    "decision": 0.9,
    "idea": 0.7,
    "preference": 0.8,
    "interest": 0.8,
    "likes": 0.8,
    "loves": 0.8,
    "dislikes": 0.8,
    "enjoys": 0.8,
    "relationship": 0.5,
    "other": 0.5,
}

SUBJECT_PRONOUNS = {
    "it",
    "this",
    "that",
    "they",
    "them",
    "he",
    "she",
}

PROJECT_DECISION_QUERY = re.compile(
    r"^(?:what|which)\s+"
    r"(?P<domain>hardware|components?|parts)\s+"
    r"(?:have|did)\s+i\s+(?:explicitly\s+)?"
    r"(?:choose|chose|chosen|pick|picked|select|selected|"
    r"decide on|decided on)\s+for\s+(?:my\s+)?"
    r"(?P<project>[a-z0-9][a-z0-9 _-]*?)[?.!]*$",
    re.IGNORECASE,
)


def get_importance(category):
    """Return the importance score for a memory category."""
    return IMPORTANCE_SCORES.get(category, 0.5)


def _timestamp():
    return datetime.now(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def remember_memory(
    key,
    value,
    category="other",
    importance=None,
    subject="user",
    status="stated",
    correction=False,
):
    """Store a memory while preserving its subject and metadata."""
    key = str(key).strip()
    value = str(value).strip()
    category = str(category).strip().lower()
    subject = str(subject).strip() or "user"
    status = str(status).strip().lower()

    if not key or not value:
        return None
    if status not in MEMORY_STATUSES:
        raise ValueError(f"Unsupported memory status '{status}'.")

    if importance is None:
        importance = get_importance(category)
    if (
        isinstance(importance, bool)
        or not isinstance(importance, (int, float))
        or not math.isfinite(importance)
        or not 0 <= importance <= 1
    ):
        raise ValueError("Memory importance must be between 0 and 1.")

    if subject.lower() == "user":
        remember(key, value, category, importance, status)
        stored_memories = load_memory()["memories"]
        stored = next(
            (
                memory
                for memory in stored_memories
                if str(memory.get("key", "")).casefold() == key.casefold()
                and str(memory.get("category", "")).casefold()
                == category.casefold()
                and str(memory.get("value", "")).casefold()
                == value.casefold()
                and memory.get("status", "stated") == status
            ),
            None,
        )
        if stored is None:
            stored = next(
                (
                    memory
                    for memory in stored_memories
                    if str(memory.get("key", "")).casefold()
                    == key.casefold()
                    and str(memory.get("category", "")).casefold()
                    == category.casefold()
                ),
                None,
            )
        if stored is None:
            return None
        return {
            "subject": "user",
            "key": stored["key"],
            "value": stored["value"],
            "category": stored["category"],
            "importance": stored["importance"],
            "status": stored.get("status", "stated"),
        }

    memory = load_memory()
    now = _timestamp()

    new_memory = {
        "id": str(uuid.uuid4()),
        "subject": subject,
        "predicate": key,
        "key": key,
        "value": value,
        "category": category,
        "importance": importance,
        "created_at": now,
        "updated_at": now,
        "source": "user",
        "status": status,
    }

    if category in MULTI_VALUE_CATEGORIES:
        for stored_memory in memory["memories"]:
            stored_key = str(
                stored_memory.get("key", "")
            ).strip().lower()
            stored_value = str(
                stored_memory.get("value", "")
            ).strip().lower()
            stored_category = str(
                stored_memory.get("category", "")
            ).strip().lower()
            stored_subject = str(
                stored_memory.get("subject", "user")
            ).strip()

            if (
                stored_key == key.lower()
                and stored_value == value.lower()
                and stored_category == category
                and stored_subject == subject
            ):
                stored_status = stored_memory.get("status", "stated")
                if stored_status != status:
                    history = list(stored_memory.get("history", []))
                    history.append(
                        {
                            "value": stored_memory["value"],
                            "status": stored_status,
                            "updated_at": stored_memory["updated_at"],
                        }
                    )
                    new_memory["id"] = stored_memory["id"]
                    new_memory["created_at"] = stored_memory["created_at"]
                    new_memory["history"] = history
                    stored_memory.update(new_memory)
                    save_memory(memory)
                return {
                    "subject": stored_subject,
                    "key": key,
                    "value": value,
                    "category": category,
                    "importance": importance,
                    "status": status,
                }

        memory["memories"].append(new_memory)
        save_memory(memory)

        return {
            "subject": subject,
            "key": key,
            "value": value,
            "category": category,
            "importance": importance,
            "status": status,
        }

    for stored_memory in memory["memories"]:
        stored_key = str(
            stored_memory.get("key", "")
        ).strip().lower()
        stored_category = str(
            stored_memory.get("category", "")
        ).strip().lower()
        stored_subject = str(
            stored_memory.get("subject", "user")
        ).strip()

        if (
            stored_key == key.lower()
            and stored_category == category
            and stored_subject == subject
        ):
            if (
                stored_memory.get("value", "").strip().casefold()
                == value.casefold()
                and stored_memory.get("status", "stated") == status
            ):
                return stored_memory

            if (
                stored_memory.get("status") == "decision"
                and status != "decision"
            ):
                return stored_memory

            if not correction:
                continue

            history = list(stored_memory.get("history", []))
            history.append(
                {
                    "value": stored_memory["value"],
                    "status": stored_memory.get("status", "stated"),
                    "updated_at": stored_memory["updated_at"],
                }
            )
            new_memory["history"] = history
            new_memory["id"] = stored_memory["id"]
            new_memory["created_at"] = stored_memory["created_at"]
            stored_memory.update(new_memory)
            save_memory(memory)

            return {
                "subject": subject,
                "key": key,
                "value": value,
                "category": category,
                "importance": importance,
                "status": status,
            }

    memory["memories"].append(new_memory)
    save_memory(memory)

    return {
        "subject": subject,
        "key": key,
        "value": value,
        "category": category,
        "importance": importance,
        "status": status,
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


def is_project_decision_query(user_input):
    """Identify requests for explicit choices associated with a project."""
    return (
        isinstance(user_input, str)
        and PROJECT_DECISION_QUERY.match(user_input.strip()) is not None
    )


def extract_after_prefix(text, prefix):
    value = text[len(prefix):].strip()
    return value if value else None


def clean_memory_value(value):
    if not value:
        return None

    value = value.strip().rstrip(".,!? ")
    return value if value else None


def _looks_temporary_statement(text):
    lowered = text.lower()

    temporary_patterns = (
        "today",
        "right now",
        "currently",
        "this morning",
        "tonight",
        "yesterday",
        "tomorrow",
        "for now",
        "i'm tired",
        "i am tired",
        "i'm hungry",
        "i am hungry",
        "at school",
        "it's raining",
        "it is raining",
    )

    return any(pattern in lowered for pattern in temporary_patterns)


def _normalize_entity(value):
    value = str(value or "").strip().strip("'\"")

    if not value:
        return None

    return value.rstrip(".,!?")


def _entity_matches(query_entity, candidate):
    query_text = _normalize_entity(query_entity)
    candidate_text = _normalize_entity(candidate)
    if query_text:
        query_text = re.sub(
            r"^(?:my|the|your|a|an)\s+",
            "",
            query_text,
            flags=re.IGNORECASE,
        ).strip()
    if candidate_text:
        candidate_text = re.sub(
            r"^(?:my|the|your|a|an)\s+",
            "",
            candidate_text,
            flags=re.IGNORECASE,
        ).strip()

    if not query_text or not candidate_text:
        return False

    if query_text.casefold() == candidate_text.casefold():
        return True

    if query_text.casefold() in candidate_text.casefold():
        return True

    if candidate_text.casefold() in query_text.casefold():
        return True

    query_tokens = set(re.findall(r"[a-z0-9]+", query_text.lower()))
    candidate_tokens = set(re.findall(r"[a-z0-9]+", candidate_text.lower()))
    if not query_tokens or not candidate_tokens:
        return False

    return query_tokens.issubset(candidate_tokens) or candidate_tokens.issubset(query_tokens)


def _normalize_relation_name(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")

    return value or "relationship"


def _build_fact(
    subject,
    predicate,
    value,
    category="other",
    importance=None,
    status=None,
):
    subject = _normalize_entity(subject) or "user"
    subject = re.sub(
        r"^(?:my|the|your|a|an)\s+",
        "",
        subject,
        flags=re.IGNORECASE,
    ).strip()
    value = _normalize_entity(value)

    if value is None:
        return None

    if importance is None:
        importance = get_importance(category.lower())

    if status is None:
        status = {
            "decision": "decision",
            "idea": "idea",
            "interest": "interest",
            "preference": "preference",
            "goal": "plan",
            "aspiration": "plan",
        }.get(category.lower(), "stated")

    key = (
        predicate
        if isinstance(predicate, str) and predicate.strip()
        else subject
    )

    return {
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "category": category,
        "importance": importance,
        "key": key,
        "status": status,
    }


def _extract_fact_from_patterns(text):
    lowered = text.lower().strip()

    quoted_delimiters = {'"', "\u201c", "\u201d"}
    is_wrapped_quote = (
        len(text) >= 2
        and text[0] in quoted_delimiters
        and text[-1] in quoted_delimiters
    )

    if (
        not lowered
        or text.rstrip().endswith("?")
        or _looks_temporary_statement(text)
        or lowered.startswith(("if ", "what if ", "suppose "))
        or is_wrapped_quote
        or re.match(
            r"^(?:(?:my|the|a|an)\s+)?"
            r"(?:fictional|imaginary|hypothetical|made[- ]up)\b",
            lowered,
        )
        or re.search(
            r"\b(?:in|for)\s+(?:my|a)\s+(?:story|novel|fiction)\b",
            lowered,
        )
    ):
        return []

    correction = bool(
        re.match(
            r"^(?:actually|correction|to correct that|i changed my mind)"
            r"\s*[:,]?\s*",
            text,
            flags=re.IGNORECASE,
        )
    )
    text = re.sub(
        r"^(?:actually|correction|to correct that|i changed my mind)"
        r"\s*[:,]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    lowered = text.lower().strip()
    facts = []

    idea_match = re.match(
        r"^(?:i\s*['’]?m|i\s+am)\s+considering\s+"
        r"(?P<value>.+?)\s+for\s+(?:my\s+)?"
        r"(?P<project>[A-Za-z0-9][A-Za-z0-9 _-]*)[.!]?$",
        text,
        re.IGNORECASE,
    )
    if idea_match:
        value = clean_memory_value(idea_match.group("value"))
        project = clean_memory_value(idea_match.group("project"))
        if value and project:
            facts.append(
                _build_fact(
                    project,
                    "considered_component",
                    value,
                    "idea",
                    status="idea",
                )
            )

    completed_match = re.match(
        r"^i\s+(?:completed|finished)\s+"
        r"(?:(?:building|making)\s+)?(?P<value>.+)$",
        text,
        re.IGNORECASE,
    )
    if completed_match:
        value = clean_memory_value(completed_match.group("value"))
        if value:
            facts.append(
                _build_fact(
                    "user",
                    "project",
                    value,
                    "project",
                    status="completed",
                )
            )

    # Preserve explicit first-person choices, but only call them components
    # when the user explicitly identifies their domain.
    decision_match = re.match(
        r"^i\s+(?:(?:have|had)\s+)?"
        r"(?:choose|chose|chosen|pick|picked|select|selected|"
        r"decide\s+on|decided\s+on)\s+"
        r"(?P<value>.+?)"
        r"(?:\s+as\s+(?:a\s+)?"
        r"(?P<kind>hardware(?:\s+component)?|components?|parts?))?"
        r"\s+for\s+(?:my\s+)?"
        r"(?P<project>[A-Za-z0-9][A-Za-z0-9 _-]*)[.!?]?$",
        text,
        re.IGNORECASE,
    )

    if decision_match:
        project = clean_memory_value(decision_match.group("project"))
        value = clean_memory_value(decision_match.group("value"))

        if project and value:
            facts.append(
                _build_fact(
                    project,
                    (
                        "chosen_component"
                        if decision_match.group("kind")
                        else "chosen_option"
                    ),
                    value,
                    "decision",
                    status="decision",
                )
            )

    # Favorite facts:
    # "My favorite color is blue."
    favorite_match = re.match(
        r"^(?:my\s+)?favorite\s+"
        r"(?P<subject>[A-Za-z0-9 _-]+?)\s+is\s+"
        r"(?P<value>.+)$",
        text,
        re.IGNORECASE,
    )

    if favorite_match:
        subject = favorite_match.group("subject").strip()
        value = clean_memory_value(favorite_match.group("value"))

        if subject and value:
            facts.append(
                _build_fact(
                    "user",
                    f"favorite {subject}",
                    value,
                    "preference",
                )
            )

    # Learning over time:
    # "I've been learning robotics."
    if re.match(
        r"^(?:i\s*['’]?m|i\s+am|i've|i\s+have|i\s+can)"
        r"\s+been\s+learning\s+.+$",
        text,
        re.IGNORECASE,
    ):
        value = clean_memory_value(
            re.sub(
                r"^(?:i\s*['’]?m|i\s+am|i've|i\s+have)"
                r"\s+been\s+learning\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
        )

        if value:
            facts.append(
                _build_fact("user", "interests", value, "interest")
            )

    # "I'm learning Python." / "I am studying electronics."
    if re.match(
        r"^(?:i\s*['’]?m|i\s+am|i've|i\s+have)"
        r"\s+(?:learning|studying)\s+.+$",
        text,
        re.IGNORECASE,
    ):
        value = clean_memory_value(
            re.sub(
                r"^(?:i\s*['’]?m|i\s+am|i've|i\s+have)"
                r"\s+(?:learning|studying)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
        )

        if value:
            facts.append(
                _build_fact("user", "interests", value, "interest")
            )

    # Projects:
    # "I'm building a robotic arm with Arduino."
    if re.match(
        r"^(?:i\s*['’]?m|i\s+am|i've|i\s+have)"
        r"\s+(?:working on|building|planning to build)\s+.+$",
        text,
        re.IGNORECASE,
    ):
        value = clean_memory_value(
            re.sub(
                r"^(?:i\s*['’]?m|i\s+am|i've|i\s+have)"
                r"\s+(?:working on|building|planning to build)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
        )

        if value:
            facts.append(
                _build_fact(
                    "user",
                    "project",
                    value,
                    "project",
                    status=(
                        "plan"
                        if "planning to build" in lowered
                        else "in_progress"
                    ),
                )
            )

    # Interests:
    # "I'm interested in robotics."
    if re.match(
        r"^(?:i\s*['’]?m|i\s+am|i've|i\s+have)"
        r"\s+interested\s+in\s+.+$",
        text,
        re.IGNORECASE,
    ):
        value = clean_memory_value(
            re.sub(
                r"^(?:i\s*['’]?m|i\s+am|i've|i\s+have)"
                r"\s+interested\s+in\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
        )

        if value:
            facts.append(
                _build_fact("user", "interests", value, "interest")
            )

    into_match = re.match(
        r"^(?:i\s*['’]?m|i\s+am)\s+(?:really\s+)?into\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if into_match:
        value = clean_memory_value(into_match.group(1))
        if value:
            facts.append(
                _build_fact("user", "interests", value, "interest")
            )

    # Preferences and dislikes.
    preference_prefixes = (
        "i really like ",
        "i like ",
        "i really love ",
        "i love ",
        "i enjoy ",
        "i prefer ",
        "i hate ",
    )

    for prefix in preference_prefixes:
        if lowered.startswith(prefix):
            value = clean_memory_value(text[len(prefix):])

            if value:
                if prefix in ("i like ", "i really like "):
                    category, label = "likes", "likes"
                elif prefix in ("i love ", "i really love "):
                    category, label = "loves", "loves"
                elif prefix == "i enjoy ":
                    category, label = "enjoys", "enjoys"
                elif prefix == "i prefer ":
                    category, label = "preference", "preferences"
                else:
                    category, label = "dislikes", "dislikes"

                facts.append(
                    _build_fact("user", label, value, category)
                )

            break

    # Goals:
    # "My long-term goal is to become a computer engineer."
    goal_match = re.match(
        r"^(?:my\s+)?(?:(?:long[- ]term|long\s+term)\s+)?"
        r"(?:goal\s+is\s+(?:to\s+)?|goal\s+is|"
        r"i\s+want\s+to|i\s+hope\s+to|i\s+plan\s+to)\s+"
        r"(?P<value>.+)$",
        text,
        re.IGNORECASE,
    )

    if goal_match:
        value = clean_memory_value(goal_match.group("value"))

        if value:
            facts.append(
                _build_fact("user", "goal", value, "goal", status="plan")
            )

    hardware_match = re.match(
        r"^(?:my\s+)?(?P<subject>[A-Za-z0-9][A-Za-z0-9 _-]*)\s+"
        r"(?:uses|runs\s+on|has)\s+(?P<value>.+)$",
        text,
        re.IGNORECASE,
    )

    if hardware_match:
        subject = hardware_match.group("subject").strip()
        value = clean_memory_value(hardware_match.group("value"))
        if subject and value:
            facts.append(
                _build_fact(
                    subject,
                    "uses",
                    value,
                    "project",
                    status="stated",
                )
            )

    # Identity:
    # "My name is Quen."
    if re.match(
        r"^(?:my\s+)?name\s+is\s+.+$",
        text,
        re.IGNORECASE,
    ):
        value = clean_memory_value(
            re.sub(
                r"^(?:my\s+)?name\s+is\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
        )

        if value:
            facts.append(
                _build_fact("user", "name", value, "identity")
            )

    # Location:
    # "I live in Dinalupihan."
    if re.match(
        r"^(?:i\s+live\s+in|i\s+am\s+from)\s+.+$",
        text,
        re.IGNORECASE,
    ):
        value = clean_memory_value(
            re.sub(
                r"^(?:i\s+live\s+in|i\s+am\s+from)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
        )

        if value:
            facts.append(
                _build_fact("user", "location", value, "location")
            )

    # Relationships:
    # "AXIS is a subsystem of ATLAS."
    # "AXIS will be a subsystem of ATLAS."
    relation_match = re.match(
        r"^(?:the\s+)?"
        r"(?P<subject>[A-Za-z0-9][A-Za-z0-9 _-]*)\s+"
        r"(?:is|are|was|were|will\s+be)\s+"
        r"(?:a\s+)?"
        r"(?P<descriptor>subsystem(?:\s+(?:of|for))?|"
        r"robotic\s+arm(?:\s+for)?)\s+"
        r"(?P<object>[A-Za-z0-9][A-Za-z0-9 _-]*)[.!?]?$",
        text,
        re.IGNORECASE,
    )

    if relation_match:
        subject = relation_match.group("subject").strip()
        object_value = relation_match.group("object").strip()
        descriptor = relation_match.group("descriptor").lower()

        predicate = (
            "subsystem_of"
            if descriptor.startswith("subsystem")
            else "robotic_arm_for"
        )

        facts.append(
            _build_fact(
                subject,
                predicate,
                object_value,
                "relationship",
            )
        )

    # Naming:
    # "The robotic arm will be called AXIS."
    # "My test robot is named Copperhead."
    name_match = re.match(
        r"^(?:my\s+|the\s+|your\s+)?"
        r"(?P<subject>.+?)\s+"
        r"(?:will\s+be\s+called|is\s+called|is\s+named|was\s+called|was\s+named)\s+"
        r"(?P<value>[A-Za-z0-9][A-Za-z0-9 _-]*)[.!?]?$",
        text,
        re.IGNORECASE,
    )

    if name_match:
        subject = name_match.group("subject").strip()
        value = clean_memory_value(name_match.group("value"))

        if subject and value:
            facts.append(
                _build_fact(
                    subject,
                    "name",
                    value,
                    "project",
                    status="plan"
                    if "will" in name_match.group(0).lower()
                    else "stated",
                )
            )

    possessive_name_match = re.match(
        r"^(?:my|the|your)\s+"
        r"(?P<subject>[A-Za-z0-9][A-Za-z0-9 _-]*?)['’]s\s+"
        r"name\s+is\s+"
        r"(?P<value>[A-Za-z0-9][A-Za-z0-9 _'’-]*)[.!?]?$",
        text,
        re.IGNORECASE,
    )
    if possessive_name_match:
        subject = possessive_name_match.group("subject").strip()
        value = clean_memory_value(possessive_name_match.group("value"))
        if subject and value:
            facts.append(
                _build_fact(subject, "name", value, "project")
            )

    # "DUM-E is the robotic arm for ATLAS."
    descriptor_match = re.match(
        r"^(?:the\s+)?"
        r"(?P<subject>[A-Za-z0-9][A-Za-z0-9 _-]*)\s+"
        r"(?:is|are)\s+(?:the\s+)?"
        r"(?P<descriptor>robotic\s+arm|subsystem)\s+for\s+"
        r"(?P<object>[A-Za-z0-9][A-Za-z0-9 _-]*)[.!?]?$",
        text,
        re.IGNORECASE,
    )

    if descriptor_match:
        subject = descriptor_match.group("subject").strip()
        object_value = descriptor_match.group("object").strip()
        descriptor = descriptor_match.group("descriptor").lower()

        predicate = (
            "subsystem_of"
            if "subsystem" in descriptor
            else "robotic_arm_for"
        )

        facts.append(
            _build_fact(
                subject,
                predicate,
                object_value,
                "relationship",
                status=(
                    "plan"
                    if re.search(r"\bwill\s+be\b", text, re.IGNORECASE)
                    else "stated"
                ),
            )
        )

    facts = [fact for fact in facts if fact is not None]
    if correction:
        for fact in facts:
            fact["correction"] = True
    return facts


def _is_subject_pronoun(subject):
    return str(subject or "").strip().lower() in SUBJECT_PRONOUNS


def _resolve_relationship_subject(fact, previous_entity):
    """Resolve a relationship pronoun only when an antecedent is known."""
    if fact.get("category") != "relationship":
        return fact

    subject = fact.get("subject", "")

    if not _is_subject_pronoun(subject):
        return fact

    if not previous_entity:
        return None

    resolved = dict(fact)
    resolved["subject"] = previous_entity

    return resolved


def _entity_from_facts(facts):
    """Get the most recently introduced entity from extracted facts."""
    for fact in reversed(facts):
        if fact.get("category") not in {"project", "relationship"}:
            continue

        if fact.get("predicate") == "name":
            return _normalize_entity(fact.get("value"))

        subject = _normalize_entity(fact.get("subject"))

        if subject and subject.lower() != "user":
            if not _is_subject_pronoun(subject):
                return subject

    return None


def extract_facts(user_input):
    """Extract durable facts and resolve simple, unambiguous pronouns."""
    if not isinstance(user_input, str):
        return []

    text = user_input.strip()

    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+|;\s*", text)

    facts = []
    previous_entity = None

    clauses = []
    for sentence in sentences:
        clauses.extend(
            re.split(
                r"\s+and\s+(?=(?:i\b|my\s+(?:favorite|name|goal|project)\b))",
                sentence,
                flags=re.IGNORECASE,
            )
        )

    for sentence in clauses:
        sentence = sentence.strip()

        if not sentence:
            continue

        sentence_facts = _extract_fact_from_patterns(sentence)
        resolved_facts = []

        for fact in sentence_facts:
            resolved = _resolve_relationship_subject(
                fact,
                previous_entity,
            )

            if resolved is not None:
                resolved_facts.append(resolved)

        facts.extend(resolved_facts)

        entity = _entity_from_facts(resolved_facts)

        if entity:
            previous_entity = entity

    deduped = []
    seen = set()

    for fact in facts:
        key = (
            fact.get("subject"),
            fact.get("predicate"),
            fact.get("value"),
            fact.get("category"),
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(fact)

    return deduped


def detect_memory(user_input):
    """Return a compact representation of extracted facts."""
    facts = extract_facts(user_input)

    if not facts:
        return None

    if len(facts) == 1:
        fact = facts[0]

        return (
            fact.get("key"),
            fact.get("value"),
            fact.get("category"),
        )

    return [
        (
            fact.get("key"),
            fact.get("value"),
            fact.get("category"),
        )
        for fact in facts
    ]


def save_fact(fact, project_name="ATLAS"):
    """Persist one extracted fact in its personal or project memory store."""
    key = fact.get("key") or fact.get("predicate")
    value = fact.get("value")
    category = fact.get("category", "other")
    importance = fact.get("importance")
    subject = fact.get("subject", "user")
    status = fact.get("status", "stated")

    if not key or value is None:
        return None

    if str(subject).strip().casefold() == "user":
        return remember_memory(
            key,
            value,
            category=category,
            importance=importance,
            subject="user",
            status=status,
        )

    save_options = {
        "category": category,
        "importance": importance if importance is not None else 0.5,
        "status": status,
    }
    if fact.get("correction"):
        save_options["correction"] = True
    return remember_project_fact(
        project_name,
        subject,
        fact.get("predicate") or key,
        value,
        **save_options,
    )


def process_memory(user_input, project_name="ATLAS"):
    """Extract and save facts in the same stores used by the Atlas runtime."""
    saved = [
        result
        for fact in extract_facts(user_input)
        if (result := save_fact(fact, project_name)) is not None
    ]

    if not saved:
        return None

    return saved[0] if len(saved) == 1 else saved


def _find_entity_name(entity, project_name=None):
    lookup = _normalize_entity(entity)
    if not lookup:
        return None

    records = [
        record
        for record in get_memories() + get_project_facts(project_name)
        if str(record.get("predicate") or record.get("key") or "")
        .strip()
        .casefold()
        == "name"
    ]

    exact_matches = [
        record
        for record in records
        if _normalize_entity(record.get("subject")) is not None
        and _normalize_entity(record.get("subject")).casefold()
        == lookup.casefold()
    ]
    matches = exact_matches or [
        record
        for record in records
        if _entity_matches(lookup, record.get("subject"))
    ]

    values = {
        str(record.get("value", "")).strip().casefold()
        for record in matches
        if str(record.get("value", "")).strip()
    }
    if len(values) != 1:
        return None

    matches.sort(
        key=lambda record: str(record.get("updated_at", "")),
        reverse=True,
    )
    return str(matches[0].get("value", "")).strip() or None


def query_memory(user_input, project_name=None):
    """Answer supported memory queries without calling the AI model."""
    if not isinstance(user_input, str):
        return None

    text = user_input.strip()
    lowered = text.lower()
    normalized = lowered.rstrip("?").strip()

    decision_query = PROJECT_DECISION_QUERY.match(text)

    if decision_query:
        domain = decision_query.group("domain").strip()
        project = decision_query.group("project").strip()
        project_facts = get_project_facts(project_name)
        choices = [
            str(fact.get("value", "")).strip()
            for fact in project_facts
            if str(fact.get("subject", "")).strip().casefold()
            == project.casefold()
            and str(fact.get("predicate", "")).strip().casefold()
            == "chosen_component"
            and fact.get("category") == "decision"
            and fact.get("status") == "decision"
            and str(fact.get("value", "")).strip()
        ]

        if choices:
            return (
                f"You chose {', '.join(choices)} for {project}."
            )

        item_label = (
            "hardware components"
            if domain.casefold() == "hardware"
            else (
                "components"
                if domain.casefold().startswith("component")
                else "parts"
            )
        )

        return (
            f"I don't have any {item_label} recorded as chosen "
            f"for {project}."
        )

    memory_about_match = re.match(
        r"^(?:what do you remember about|what do you know about|"
        r"what did i tell you about)\s+(?P<entity>.+)$",
        normalized,
        re.IGNORECASE,
    )
    if memory_about_match:
        entity = memory_about_match.group("entity").strip()
        if entity.casefold() != "me":
            lookup_entity = entity
            if lookup_entity.casefold().startswith("my "):
                lookup_entity = lookup_entity[3:].strip()
            generic_keys = {
                "project",
                "projects",
                "interest",
                "interests",
                "goal",
                "goals",
                "preference",
                "preferences",
                "memory",
                "memories",
                "fact",
                "facts",
            }
            matches = [
                memory
                for memory in get_memories()
                if (
                    str(memory.get("subject", "")).strip().casefold()
                    == lookup_entity.casefold()
                    or str(memory.get("value", "")).strip().casefold()
                    == lookup_entity.casefold()
                    or (
                        lookup_entity.casefold() not in generic_keys
                        and any(
                            str(memory.get(field, "")).strip().casefold()
                            == lookup_entity.casefold()
                            for field in ("predicate", "key")
                        )
                    )
                )
            ]
            matches.extend(
                fact
                for fact in get_project_facts(project_name)
                if any(
                    str(fact.get(field, "")).strip().casefold()
                    == lookup_entity.casefold()
                    for field in ("subject", "value")
                )
            )
            if matches:
                return (
                    f"Recorded facts about {lookup_entity}: "
                    + "; ".join(
                        f"{fact.get('predicate', fact.get('key', 'related'))} "
                        f"{fact.get('value', '')}"
                        for fact in matches
                    )
                    + "."
                )
            return (
                f"I don't have anything recorded about {lookup_entity}."
            )

    name_query_match = None
    for pattern in (
        r"^(?:what(?:'s|\s+is)\s+)(?:my\s+|the\s+|your\s+)?(?P<entity>.+?)\s+(?:named|called)\??$",
        r"^(?:what(?:'s|\s+is)\s+the\s+name\s+of\s+)(?:my\s+|the\s+|your\s+)?(?P<entity>.+?)\??$",
        r"^(?:what(?:'s|\s+is)\s+)(?:my\s+|the\s+|your\s+)"
        r"(?P<entity>.+?)['’]s\s+name\??$",
    ):
        name_query_match = re.match(pattern, normalized, re.IGNORECASE)
        if name_query_match:
            break

    if name_query_match:
        entity = _normalize_entity(name_query_match.group("entity")) or ""
        if entity:
            name = _find_entity_name(entity, project_name=project_name)
            if name:
                return f"Your {entity} is named {name}."
            return f"I don't have a recorded name for {entity}."

    remember_entity_match = re.match(
        r"^(?:do\s+you\s+remember|do\s+you\s+still\s+remember|do\s+you\s+know)\s+(?:my\s+|the\s+|your\s+)?(?P<entity>.+?)\??$",
        normalized,
        re.IGNORECASE,
    )
    if remember_entity_match:
        entity = _normalize_entity(remember_entity_match.group("entity")) or ""
        if entity:
            name = _find_entity_name(entity, project_name=project_name)
            if name:
                return f"Yes - your {entity} is named {name}."
            return f"I don't have any memory of your {entity}."

    if normalized in {
        "what are my latest projects",
        "what are my most recent projects",
        "what are my two latest projects",
        "what are my two most recent projects",
    }:
        projects = get_memories_by_category("project")
        ordered = sorted(
            enumerate(projects),
            key=lambda item: (
                str(item[1].get("updated_at", item[1].get("created_at", ""))),
                item[0],
            ),
            reverse=True,
        )
        latest = []
        seen = set()
        for _, memory in ordered:
            value = str(memory.get("value", "")).strip()
            if value and value.casefold() not in seen:
                latest.append(value)
                seen.add(value.casefold())
            if len(latest) == 2:
                break
        return (
            "Your latest projects are: " + ", ".join(latest) + "."
            if latest
            else "I don't have any projects stored in my memory."
        )

    entity_match = re.match(
        r"^(?:what is|what's)\s+(?P<entity>.+)$",
        normalized,
        re.IGNORECASE,
    )
    if entity_match:
        entity = entity_match.group("entity").strip()
        facts = get_project_facts(project_name)
        matches = [
            fact
            for fact in facts
            if str(fact.get("subject", "")).strip().casefold()
            == entity.casefold()
        ]
        if matches:
            display_entity = matches[0].get("subject", entity)
            return (
                f"Recorded facts about {display_entity}: "
                + "; ".join(
                    f"{fact.get('predicate', 'related')} "
                    f"{fact.get('value', '')}"
                    for fact in matches
                )
                + "."
            )

    if normalized == "what are my favorites":
        memories = get_memories_by_category("preference")
        responses = []

        for memory in memories:
            key = memory.get("key", "")
            value = memory.get("value", "")

            if key.startswith("favorite "):
                subject = key[len("favorite "):]
                responses.append(
                    f"Your favorite {subject} is {value}."
                )

        return (
            " ".join(responses)
            if responses
            else "I don't have any favorites stored in my memory."
        )

    if normalized in ("what do i like", "what do you know i like"):
        categories = {
            "preference",
            "likes",
            "loves",
            "dislikes",
            "enjoys",
        }

        memories = [
            memory
            for memory in get_memories()
            if memory.get("category") in categories
        ]

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
                responses.append(
                    f"Your favorite {subject} is {value}."
                )

        return (
            " ".join(responses)
            if responses
            else "I don't have any preferences about you in my memory."
        )

    if normalized.startswith("what is my favorite "):
        subject = text[len("what is my favorite "):].rstrip("?").strip()

        if not subject:
            return None

        value = recall_memory(f"favorite {subject}")

        return (
            f"Your favorite {subject} is {value}."
            if value is not None
            else f"I don't have your favorite {subject} in my memory."
        )

    if normalized.startswith("what's my favorite "):
        subject = text[len("what's my favorite "):].rstrip("?").strip()

        if not subject:
            return None

        value = recall_memory(f"favorite {subject}")

        return (
            f"Your favorite {subject} is {value}."
            if value is not None
            else f"I don't have your favorite {subject} in my memory."
        )

    if normalized in ("what is my name", "what's my name"):
        value = recall_memory("name")

        return (
            f"Your name is {value}."
            if value is not None
            else "I don't have your name in my memory."
        )

    if normalized == "where do i live":
        value = recall_memory("location")

        return (
            f"You live in {value}."
            if value is not None
            else "I don't have your location in my memory."
        )

    if normalized in (
        "what project am i working on",
        "what am i working on",
        "what projects am i working on",
        "what projects do i have",
    ):
        projects = get_memories_by_category("project")
        values = [project.get("value", "") for project in projects]

        return (
            "Your projects include: " + ", ".join(values) + "."
            if values
            else "I don't have any projects stored in my memory."
        )

    if normalized in ("what am i interested in", "what are my interests"):
        interests = get_memories_by_category("interest")
        values = [interest.get("value", "") for interest in interests]

        return (
            "You're interested in: " + ", ".join(values) + "."
            if values
            else "I don't have any interests about you in my memory."
        )

    if normalized in ("what are my goals", "what are my goals in life"):
        goals = get_memories_by_category("goal")
        values = [goal.get("value", "") for goal in goals]

        return (
            "Your goals include: " + ", ".join(values) + "."
            if values
            else "I don't have any goals stored in my memory."
        )

    if normalized == "what are my aspirations":
        aspirations = get_memories_by_category("aspiration")
        values = [
            aspiration.get("value", "")
            for aspiration in aspirations
        ]

        return (
            "Your aspirations include: " + ", ".join(values) + "."
            if values
            else "I don't have any aspirations stored in my memory."
        )

    if normalized == "what do you remember about me":
        memories = get_memories()

        if not memories:
            return "I don't have anything stored about you yet."

        lines = [
            f"- {memory.get('key', 'unknown')}: "
            f"{memory.get('value', '')}"
            for memory in memories
        ]

        return "Here's what I remember about you:\n" + "\n".join(lines)

    if " related to" in normalized:
        entity = normalized.split(" related to", 1)[0]

        if entity.startswith("what is "):
            entity = entity[8:].strip()

        matches = []

        for memory in get_memories():
            subject = str(memory.get("subject", "")).strip()
            value = str(memory.get("value", "")).strip()

            if (
                entity.lower() == subject.lower()
                or entity.lower() == value.lower()
            ):
                matches.append(memory)

        if matches:
            return "Related facts: " + "; ".join(
                f"{memory.get('subject', 'unknown')} "
                f"{memory.get('predicate', '')} "
                f"{memory.get('value', '')}"
                for memory in matches
            )

    if normalized.startswith("what is "):
        entity = normalized[8:].strip().rstrip("?").strip()

        if entity:
            matches = []

            for memory in get_memories():
                subject = str(memory.get("subject", "")).strip()
                value = str(memory.get("value", "")).strip()
                key = str(memory.get("key", "")).strip()

                if (
                    entity.lower() == subject.lower()
                    or entity.lower() == key.lower()
                    or entity.lower() in value.lower()
                ):
                    matches.append(memory)

            if matches:
                lines = [
                    f"{memory.get('subject', 'unknown')} "
                    f"{memory.get('predicate', '')}: "
                    f"{memory.get('value', '')}"
                    for memory in matches
                ]

                return " | ".join(lines)

    return None