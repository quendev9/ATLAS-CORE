from memory.memory import remember


def classify_memory(key):
    key_lower = key.lower()

    if "favorite" in key_lower or "like" in key_lower or "love" in key_lower:
        return "preference"

    if "name" in key_lower or "i am" in key_lower or "i'm" in key_lower:
        return "identity"

    if "live" in key_lower or "from" in key_lower or "location" in key_lower:
        return "location"

    if "project" in key_lower:
        return "project"

    if "interest" in key_lower or "hobby" in key_lower or "robotics" in key_lower:
        return "interest"

    return "other"


def extract_memory(user_input):
    text = user_input.strip()

    # Pattern: "My X is Y"
    if " is " in text:
        key, value = text.split(" is ", 1)

        key = key.strip()
        value = value.strip()

        if key.lower().startswith("my "):
            return key, value

    # Pattern: "I live in X"
    if text.lower().startswith("i live in "):
        key = "I live in"
        value = text[10:].strip()

        if value:
            return key, value

    # Pattern: "I like X"
    if text.lower().startswith("i like "):
        key = "I like"
        value = text[7:].strip()

        if value:
            return key, value

    # Pattern: "I love X"
    if text.lower().startswith("i love "):
        key = "I love"
        value = text[7:].strip()

        if value:
            return key, value

    # Pattern: "I am X"
    if text.lower().startswith("i am "):
        key = "I am"
        value = text[5:].strip()

        if value:
            return key, value

    # Pattern: "I'm X"
    if text.lower().startswith("i'm "):
        key = "I'm"
        value = text[4:].strip()

        if value:
            return key, value

    return None


def process_memory(user_input):
    result = extract_memory(user_input)

    if result is None:
        return False

    key, value = result
    category = classify_memory(key)

    remember(key, value)

    print(f"[MEMORY] Saved ({category}): {key} → {value}")

    return True

if __name__ == "__main__":
    print("MEMORY SAVE TEST")
    print("-----------------")

    tests = [
        "My favorite animal is a shark",
        "I like robotics",
        "I live in Quezon City",
    ]

    for test in tests:
        print(f"\nInput: {test}")

        saved = process_memory(test)

        print(f"Saved: {saved}")