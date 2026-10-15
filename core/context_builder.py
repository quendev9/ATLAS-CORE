
import re

from memory.conversations import get_conversation
from memory.manager import get_memories
from memory.project_memory import get_project_facts


DEFAULT_CONTEXT_CHAR_LIMIT = 12000


def _normalize_project_name(project_name):
    if not project_name:
        return None

    return str(project_name).strip() or None


def _tokens(text):
    """Return normalized words for relevance matching."""
    return {
        token
        for token in re.findall(
            r"[a-zA-Z0-9][a-zA-Z0-9'-]*",
            str(text or "").lower(),
        )
        if len(token) > 2
    }


def _relevance_score(query_tokens, text):
    """Score text according to its overlap with the query."""
    if not query_tokens:
        return 0

    text_tokens = _tokens(text)
    overlap = query_tokens & text_tokens

    if not overlap:
        return 0

    coverage = len(overlap) / len(query_tokens)

    return len(overlap) * 3 + int(coverage * 5)


def _rank_memories(query, memories, limit):
    """Select personal memories most relevant to the current query."""
    query_tokens = _tokens(query)
    ranked = []

    for index, memory in enumerate(memories or []):
        if not isinstance(memory, dict):
            continue

        description = " ".join(
            str(memory.get(field, ""))
            for field in (
                "subject",
                "predicate",
                "key",
                "value",
                "category",
            )
        )

        score = _relevance_score(query_tokens, description)

        if score == 0 and memory.get("category") in {
            "identity",
            "goal",
            "aspiration",
        }:
            score = 1

        ranked.append((score, index, memory))

    ranked.sort(key=lambda item: (-item[0], item[1]))

    selected = [
        memory
        for score, _, memory in ranked
        if score > 0
    ]

    return selected[:limit]


def _rank_project_facts(query, facts, limit):
    """Select project facts most relevant to the current query."""
    query_tokens = _tokens(query)
    ranked = []

    for index, fact in enumerate(facts or []):
        if not isinstance(fact, dict):
            continue

        if not fact.get("value"):
            continue

        description = " ".join(
            str(fact.get(field, ""))
            for field in (
                "subject",
                "predicate",
                "value",
                "category",
            )
        )

        score = _relevance_score(query_tokens, description)
        recency = str(
            fact.get("updated_at", fact.get("created_at", ""))
        )
        ranked.append((score, recency, index, fact))

    # Prefer stronger matches, then newer entries when scores tie.
    ranked.sort(key=lambda item: (item[1], item[2]), reverse=True)
    ranked.sort(key=lambda item: item[0], reverse=True)

    selected = [
        fact
        for score, _, _, fact in ranked
        if score > 0
    ]

    return selected[:limit]


def _append_with_budget(sections, heading, lines, remaining):
    """Append a section without exceeding the available character budget."""
    if remaining <= 0 or not lines:
        return remaining

    heading = str(heading)
    lines = [
        str(line)
        for line in lines
        if str(line).strip()
    ]

    if not lines:
        return remaining

    section = heading + "\n" + "\n".join(lines)
    separator_length = 2

    if len(section) + separator_length <= remaining:
        sections.append(section)
        return remaining - len(section) - separator_length

    prefix = heading + "\n"

    if remaining <= len(prefix) + 20:
        return remaining

    suffix = "\n[Section shortened to fit context limit.]"
    available = remaining - len(prefix) - len(suffix) - separator_length

    if available <= 0:
        return remaining

    clipped_lines = []
    used = 0

    for line in lines:
        addition = len(line) + (1 if clipped_lines else 0)

        if used + addition > available:
            break

        clipped_lines.append(line)
        used += addition

    if clipped_lines:
        sections.append(
            prefix
            + "\n".join(clipped_lines)
            + suffix
        )
        return 0

    return remaining


def build_context(
    conversation_id,
    user_message,
    project_name=None,
    max_recent_messages=8,
    max_memory_facts=6,
    max_chars=DEFAULT_CONTEXT_CHAR_LIMIT,
):
    """
    Build relevant, size-limited context for a LEWIS response.

    Includes a validated conversation summary, recent messages,
    relevant older messages, project facts, and personal memories.
    """
    try:
        max_chars = int(max_chars)
        max_recent_messages = int(max_recent_messages)
        max_memory_facts = int(max_memory_facts)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "Context limits must be non-negative integers."
        ) from error

    if (
        max_chars < 0
        or max_recent_messages < 0
        or max_memory_facts < 0
    ):
        raise ValueError(
            "Context limits must be non-negative integers."
        )

    if max_chars == 0:
        return ""

    conversation = get_conversation(conversation_id)

    if conversation is None:
        conversation = {
            "messages": [],
            "summary": None,
            "summary_coverage": {},
            "project": project_name,
        }

    messages = conversation.get("messages", [])

    if not isinstance(messages, list):
        messages = []

    valid_messages = [
        message
        for message in messages
        if isinstance(message, dict)
    ]

    # Lewis.process() normally records the current user message before
    # building context, so do not append it a second time.
    recent_source = (
        valid_messages[-max_recent_messages:]
        if max_recent_messages
        else []
    )

    recent = [
        message
        for message in recent_source
        if str(message.get("content", "")).strip()
    ]

    recent_ids = {
        message.get("id")
        for message in recent
        if message.get("id") is not None
    }

    # Retrieve older messages by relevance rather than storage order.
    query_tokens = _tokens(user_message)
    older_ranked = []

    for index, message in enumerate(valid_messages):
        message_id = message.get("id")

        if message_id is not None and message_id in recent_ids:
            continue

        content = str(message.get("content", "")).strip()

        if not content:
            continue

        score = _relevance_score(query_tokens, content)

        if score > 0:
            older_ranked.append((score, index, message))

    # Prefer stronger matches, then more recent messages on ties.
    older_ranked.sort(
        key=lambda item: (-item[0], -item[1])
    )

    older_messages = [
        message
        for _, _, message in older_ranked[:max_recent_messages]
    ]

    selected_project = _normalize_project_name(
        project_name or conversation.get("project")
    )

    project_facts = []

    if selected_project and max_memory_facts:
        project_facts = _rank_project_facts(
            user_message,
            get_project_facts(selected_project) or [],
            max_memory_facts,
        )

    personal_memories = []

    if max_memory_facts:
        personal_memories = _rank_memories(
            user_message,
            get_memories() or [],
            max_memory_facts,
        )

    sections = []
    remaining = max_chars

    # Only use a summary when its recorded latest message still exists.
    summary = conversation.get("summary")
    coverage = conversation.get("summary_coverage") or {}
    summary_latest_id = coverage.get("latest_message_id")

    message_ids = {
        message.get("id")
        for message in valid_messages
        if message.get("id") is not None
    }

    if (
        isinstance(summary, str)
        and summary.strip()
        and summary_latest_id in message_ids
    ):
        remaining = _append_with_budget(
            sections,
            "Conversation summary:",
            [summary.strip()],
            remaining,
        )

    recent_lines = []

    for message in recent:
        role = str(message.get("role", "user")).upper()
        content = str(message.get("content", "")).strip()

        if content:
            recent_lines.append(f"{role}: {content}")

    remaining = _append_with_budget(
        sections,
        "Recent conversation:",
        recent_lines,
        remaining,
    )

    older_lines = [
        (
            f"- {str(message.get('role', 'user')).upper()}: "
            f"{str(message.get('content', '')).strip()}"
        )
        for message in older_messages
    ]

    remaining = _append_with_budget(
        sections,
        "Relevant older messages:",
        older_lines,
        remaining,
    )

    project_lines = [
        (
            f"- {fact.get('subject', 'unknown')} "
            f"{fact.get('predicate', 'related')}: "
            f"{fact.get('value', '')} "
            f"[status: {fact.get('status', 'stated')}]"
        )
        for fact in project_facts
    ]

    remaining = _append_with_budget(
        sections,
        (
            f"Relevant saved project facts ({selected_project}; "
            "user-stated, not necessarily confirmed decisions):"
        ),
        project_lines,
        remaining,
    )

    memory_lines = [
        (
            f"- {memory.get('subject', 'user')} "
            f"{memory.get('predicate', memory.get('key', 'memory'))}: "
            f"{memory.get('value', '')} "
            f"[status: {memory.get('status', 'stated')}]"
        )
        for memory in personal_memories
    ]

    _append_with_budget(
        sections,
        "Relevant saved personal facts (user-stated):",
        memory_lines,
        remaining,
    )

    context = "\n\n".join(sections).strip()

    if not context:
        return "No prior context available."

    # Final safeguard: returned context never exceeds max_chars.
    return context[:max_chars]