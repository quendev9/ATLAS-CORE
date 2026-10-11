
import sys
from pathlib import Path

# Add the ATLAS-CORE project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from memory.manager import extract_facts

def main():
    samples = [
        "My favorite color is blue.",
        "My favorite color is green.",
        "I've been learning robotics.",
        "I'm building a robotic arm with Arduino.",
        "AXIS is a subsystem of ATLAS.",
        "DUM-E is the robotic arm for ATLAS.",
        "The robotic arm will be called AXIS. It will be a subsystem of ATLAS.",
        "I'm tired today.",
        "I'm hungry right now.",
    ]

    for text in samples:
        print(f"\nINPUT: {text}")
        try:
            print("FACTS:", extract_facts(text))
        except Exception as error:
            print(f"ERROR: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()