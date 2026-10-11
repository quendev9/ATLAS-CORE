import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import subprocess
import tempfile

from memory import memory as personal_storage
from memory import project_memory as project_storage
from memory.manager import remember_memory

def main():
    with tempfile.TemporaryDirectory(prefix="atlas_memory_test_") as temp:
        temp = Path(temp)
        personal_path = temp / "memory.json"
        project_path = temp / "project_memory.json"

        # Redirect storage to temporary files, not your real memories.
        personal_storage.MEMORY_FILE = personal_path
        project_storage.PROJECT_MEMORY_FILE = project_path

        remember_memory(
            "favorite test instrument",
            "synthesizer",
            category="preference",
            importance=0.8,
        )

        project_storage.remember_project_fact(
            "ATLAS_PERSISTENCE_TEST",
            "AXIS",
            "subsystem_of",
            "ATLAS",
            category="relationship",
            importance=0.5,
        )

        assert personal_path.exists(), "Personal file was not created."
        assert project_path.exists(), "Project file was not created."

        # Verify retrieval from a completely fresh Python process.
        child_code = """
import sys
from pathlib import Path
from memory import memory as personal_storage
from memory import project_memory as project_storage
from memory.manager import recall_memory

personal_storage.MEMORY_FILE = Path(sys.argv[1])
project_storage.PROJECT_MEMORY_FILE = Path(sys.argv[2])

assert recall_memory("favorite test instrument") == "synthesizer"

facts = project_storage.get_project_facts("ATLAS_PERSISTENCE_TEST")
assert any(
    fact.get("subject") == "AXIS"
    and fact.get("predicate") == "subsystem_of"
    and fact.get("value") == "ATLAS"
    for fact in facts
)

print("PERSONAL MEMORY: PASS")
print("PROJECT MEMORY: PASS")
print("FRESH PROCESS RETRIEVAL: PASS")
"""

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                child_code,
                str(personal_path),
                str(project_path),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        if result.stdout:
            print(result.stdout, end="")

        if result.returncode != 0:
            print("PERSISTENCE TEST FAILED")
            print(result.stderr)
            raise SystemExit(result.returncode)

        print("ALL PERSISTENCE CHECKS PASSED")

if __name__ == "__main__":
    main()