import json
import os
import subprocess
import sys
import os
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from google.genai.errors import ServerError

import main as lewis_main
from core import lewis as lewis_module
from core.identity import LEWIS_IDENTITY
from core.lewis import Lewis
from memory import conversations
from memory import memory as memory_storage
from memory import project_memory as project_memory_storage
from memory.manager import (
    get_memories,
    get_memories_by_category,
    process_memory,
    query_memory,
    remember_memory,
)


class MemoryStorageTests(unittest.TestCase):
    def setUp(self):
        self.provider_patch = patch.dict(
            os.environ,
            {"AI_PROVIDER": "gemini"},
        )
        self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.memory_path = Path(self.temp_dir.name) / "memory.json"
        self.memory_file_patch = patch.object(
            memory_storage, "MEMORY_FILE", self.memory_path
        )
        self.memory_file_patch.start()
        self.addCleanup(self.memory_file_patch.stop)
        self.project_memory_path = Path(self.temp_dir.name) / "project_memory.json"
        self.project_memory_file_patch = patch.object(
            project_memory_storage,
            "PROJECT_MEMORY_FILE",
            self.project_memory_path,
        )
        self.project_memory_file_patch.start()
        self.addCleanup(self.project_memory_file_patch.stop)
        self.conversations_file_patch = patch.object(
            conversations,
            "CONVERSATIONS_FILE",
            Path(self.temp_dir.name) / "conversations.json",
        )
        self.conversations_file_patch.start()
        self.addCleanup(self.conversations_file_patch.stop)

    def test_new_memory_has_id_timestamps_and_persists(self):
        remember_memory("favorite color", "blue", "preference")

        persisted = json.loads(self.memory_path.read_text(encoding="utf-8"))
        record = persisted["memories"][0]
        uuid.UUID(record["id"])
        self.assertEqual(record["subject"], "user")
        self.assertEqual(record["predicate"], "favorite color")
        self.assertEqual(record["key"], "favorite color")
        self.assertEqual(record["source"], "user")
        self.assertEqual(record["importance"], 0.8)
        self.assertEqual(
            datetime.fromisoformat(record["created_at"].replace("Z", "+00:00")).tzinfo,
            datetime.fromisoformat(record["updated_at"].replace("Z", "+00:00")).tzinfo,
        )
        self.assertEqual(
            memory_storage.load_memory()["memories"][0]["value"], "blue"
        )

    def test_personal_and_project_memories_both_persist(self):
        remember_memory("favorite instrument", "synthesizer", "preference")
        project_memory_storage.remember_project_fact(
            "Cyberdeck",
            "Cyberdeck",
            "project",
            "a cyberdeck, any suggestions",
        )

        self.assertEqual(memory_storage.recall("favorite instrument"), "synthesizer")
        project_facts = project_memory_storage.get_project_facts("Cyberdeck")
        self.assertEqual(len(project_facts), 1)
        self.assertEqual(
            project_facts[0]["value"],
            "a cyberdeck, any suggestions",
        )

    def test_legacy_and_lewis_capture_share_project_storage_and_deduplicate(self):
        statement = "My test robot is named Copperhead."

        legacy_result = process_memory(statement)
        legacy_facts = project_memory_storage.get_project_facts("ATLAS")
        self.assertEqual(legacy_result["value"], "Copperhead")
        self.assertEqual(len(legacy_facts), 1)
        self.assertEqual(legacy_facts[0]["subject"], "test robot")
        self.assertEqual(get_memories(), [])

        lewis = Lewis()
        lewis._capture_automatic_memories(statement, "ATLAS")

        active_facts = project_memory_storage.get_project_facts("ATLAS")
        self.assertEqual(len(active_facts), 1)
        self.assertEqual(active_facts[0]["id"], legacy_facts[0]["id"])

    def test_schema_round_trips_non_user_subject_and_predicate(self):
        relation = {
            "id": str(uuid.uuid4()),
            "subject": "AXIS",
            "predicate": "subsystem_of",
            "value": "ATLAS",
            "category": "other",
            "importance": 0.5,
            "created_at": "2026-10-08T12:00:00Z",
            "updated_at": "2026-10-08T12:00:00Z",
            "source": "user",
        }

        memory_storage.save_memory({"memories": [relation]})
        stored = memory_storage.get_all_memories()[0]

        self.assertEqual(stored["subject"], "AXIS")
        self.assertEqual(stored["predicate"], "subsystem_of")
        self.assertEqual(stored["value"], "ATLAS")
        self.assertEqual(stored["key"], "subsystem_of")

    def test_legacy_memories_migrate_and_keep_fields_and_categories(self):
        original = {
            "custom_metadata": {"retained": True},
            "memories": [
                {
                    "key": "interests",
                    "value": "robotics",
                    "category": "interest",
                    "importance": 0.8,
                    "legacy_note": "preserve me",
                },
                {
                    "key": "name",
                    "value": "Quen",
                    "category": "identity",
                    "importance": 1.0,
                },
            ],
        }
        original_text = json.dumps(original, indent=2)
        self.memory_path.write_text(original_text, encoding="utf-8")

        migrated = memory_storage.load_memory()
        stored = json.loads(self.memory_path.read_text(encoding="utf-8"))
        backup = self.memory_path.with_name("memory.json.pre-v2.bak")

        self.assertEqual(backup.read_text(encoding="utf-8"), original_text)
        self.assertEqual(migrated["custom_metadata"], {"retained": True})
        self.assertEqual(stored["memories"][0]["legacy_note"], "preserve me")
        self.assertEqual(
            [record["category"] for record in stored["memories"]],
            ["interest", "identity"],
        )
        for record in stored["memories"]:
            uuid.UUID(record["id"])
            self.assertEqual(record["subject"], "user")
            self.assertEqual(record["predicate"], record["key"])
            self.assertEqual(record["source"], "user")
            self.assertTrue(record["created_at"])
            self.assertTrue(record["updated_at"])

    def test_multivalue_categories_keep_distinct_records_and_deduplicate(self):
        remember_memory("interests", "robotics", "interest")
        first_id = memory_storage.get_all_memories()[0]["id"]
        remember_memory("interests", "astronomy", "interest")
        remember_memory("interests", "ROBOTICS", "interest")

        records = memory_storage.recall_all("interests")
        self.assertEqual([record["value"] for record in records], [
            "robotics",
            "astronomy",
        ])
        self.assertEqual(records[0]["id"], first_id)

    def test_single_value_updates_keep_id_and_creation_time(self):
        remember_memory("favorite color", "blue", "preference")
        original = memory_storage.recall_all("favorite color")[0]

        remember_memory("favorite color", "green", "preference")
        updated = memory_storage.recall_all("favorite color")[0]

        self.assertEqual(updated["id"], original["id"])
        self.assertEqual(updated["created_at"], original["created_at"])
        self.assertEqual(updated["value"], "green")
        self.assertEqual(updated["history"][0]["value"], "blue")

    def test_extracted_user_correction_updates_memory_and_keeps_history(self):
        process_memory("My favorite color is blue.")
        process_memory("Actually, my favorite color is green.")

        record = memory_storage.recall_all("favorite color")[0]
        self.assertEqual(record["value"], "green")
        self.assertEqual(record["history"][0]["value"], "blue")

    def test_confirmed_decision_cannot_be_overwritten_by_a_plan(self):
        remember_memory(
            "chosen_component",
            "Raspberry Pi",
            "decision",
            status="decision",
        )
        remember_memory(
            "chosen_component",
            "Arduino",
            "decision",
            status="plan",
        )

        record = memory_storage.recall_all("chosen_component")[0]
        self.assertEqual(record["value"], "Raspberry Pi")
        self.assertEqual(record["status"], "decision")

    def test_project_lifecycle_status_updates_without_duplicate(self):
        remember_memory(
            "project",
            "cyberdeck",
            "project",
            status="plan",
        )
        remember_memory(
            "project",
            "cyberdeck",
            "project",
            status="in_progress",
        )

        records = memory_storage.recall_all("project")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "in_progress")
        self.assertEqual(records[0]["history"][0]["status"], "plan")

    def test_project_fact_corrections_update_with_history_and_deduplicate(self):
        original = project_memory_storage.remember_project_fact(
            "ATLAS",
            "Cyberdeck",
            "chosen_component",
            "Raspberry Pi",
            category="decision",
            status="decision",
        )
        duplicate = project_memory_storage.remember_project_fact(
            "ATLAS",
            "Cyberdeck",
            "chosen_component",
            "Raspberry Pi",
            category="decision",
            status="decision",
        )
        corrected = project_memory_storage.remember_project_fact(
            "ATLAS",
            "Cyberdeck",
            "chosen_component",
            "Raspberry Pi 5",
            category="decision",
            status="decision",
            correction=True,
        )

        self.assertEqual(duplicate["id"], original["id"])
        self.assertEqual(corrected["id"], original["id"])
        self.assertEqual(corrected["value"], "Raspberry Pi 5")
        self.assertEqual(corrected["history"][0]["value"], "Raspberry Pi")

    def test_project_name_updates_replace_stale_names_and_keep_history(self):
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "test robot",
            "name",
            "Copperhead",
            category="project",
        )
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "test robot",
            "name",
            "Copper",
            category="project",
        )

        facts = project_memory_storage.get_project_facts("ATLAS")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["value"], "Copper")
        self.assertEqual(facts[0]["history"][0]["value"], "Copperhead")
        self.assertEqual(
            query_memory("What is my test robot called?", project_name="ATLAS"),
            "Your test robot is named Copper.",
        )

    def test_distinct_project_decisions_are_not_treated_as_corrections(self):
        first = project_memory_storage.remember_project_fact(
            "ATLAS",
            "Cyberdeck",
            "chosen_component",
            "Raspberry Pi",
            category="decision",
            status="decision",
        )
        second = project_memory_storage.remember_project_fact(
            "ATLAS",
            "Cyberdeck",
            "chosen_component",
            "Arduino",
            category="decision",
            status="decision",
        )

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(
            [
                fact["value"]
                for fact in project_memory_storage.get_project_facts("ATLAS")
            ],
            ["Raspberry Pi", "Arduino"],
        )

    def test_idea_does_not_overwrite_a_confirmed_project_decision(self):
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "Cyberdeck",
            "chosen_component",
            "Raspberry Pi",
            category="decision",
            status="decision",
        )
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "Cyberdeck",
            "considered_component",
            "Arduino",
            category="idea",
            status="idea",
        )

        response = query_memory(
            "What hardware have I explicitly chosen for my cyberdeck?",
            project_name="ATLAS",
        )

        self.assertEqual(
            response,
            "You chose Raspberry Pi for cyberdeck.",
        )

    def test_latest_projects_are_returned_in_timestamp_order(self):
        remember_memory("project", "DUM-E", "project")
        remember_memory("project", "cyberdeck", "project")
        remember_memory("project", "older project", "project")
        stored = memory_storage.load_memory()
        stored["memories"][0]["updated_at"] = "2026-10-09T10:00:00Z"
        stored["memories"][1]["updated_at"] = "2026-10-09T11:00:00Z"
        stored["memories"][2]["updated_at"] = "2026-10-09T09:00:00Z"
        memory_storage.save_memory(stored)

        response = query_memory("What are my two latest projects?")

        self.assertEqual(
            response,
            "Your latest projects are: cyberdeck, DUM-E.",
        )

    def test_lewis_routes_latest_project_query_to_memory(self):
        remember_memory("project", "DUM-E", "project")
        remember_memory("project", "cyberdeck", "project")
        lewis = Lewis()

        with patch.object(lewis_module, "ask_ai") as ask_gemini:
            response = lewis.process("What are my two latest projects?")

        ask_gemini.assert_not_called()
        self.assertEqual(
            response,
            "Your latest projects are: cyberdeck, DUM-E.",
        )

    def test_project_fact_lookup_is_scoped_to_the_selected_project(self):
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "AXIS",
            "subsystem_of",
            "ATLAS",
            category="relationship",
        )
        project_memory_storage.remember_project_fact(
            "Other Project",
            "AXIS",
            "subsystem_of",
            "Unrelated",
            category="relationship",
        )

        response = query_memory(
            "What is AXIS?",
            project_name="ATLAS",
        )

        self.assertEqual(
            response,
            "Recorded facts about AXIS: subsystem_of ATLAS.",
        )

    def test_absent_memory_question_gets_an_honest_answer_without_ai(self):
        lewis = Lewis()
        with patch.object(lewis_module, "ask_ai") as ask_gemini:
            response = lewis.process(
                "What do you remember about MISSING-THING?"
            )

        ask_gemini.assert_not_called()
        self.assertEqual(
            response,
            "I don't have anything recorded about missing-thing.",
        )

    def test_generic_project_key_does_not_match_every_project(self):
        remember_memory("project", "DUM-E", "project")
        remember_memory("project", "cyberdeck", "project")

        response = query_memory("What do you remember about project?")

        self.assertEqual(
            response,
            "I don't have anything recorded about project.",
        )

    def test_restart_in_fresh_process_preserves_personal_and_project_memory(self):
        remember_memory("favorite instrument", "synthesizer", "preference")
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "AXIS",
            "subsystem_of",
            "ATLAS",
            category="relationship",
        )

        child_code = """
import sys
from pathlib import Path
from memory import memory, project_memory
from memory.manager import recall_memory

memory.MEMORY_FILE = Path(sys.argv[1])
project_memory.PROJECT_MEMORY_FILE = Path(sys.argv[2])
assert recall_memory("favorite instrument") == "synthesizer"
facts = project_memory.get_project_facts("ATLAS")
assert any(fact["subject"] == "AXIS" and fact["value"] == "ATLAS" for fact in facts)
"""
        environment = dict(os.environ)
        project_root = str(Path(__file__).resolve().parents[1])
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(None, [project_root, environment.get("PYTHONPATH")])
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                child_code,
                str(self.memory_path),
                str(self.project_memory_path),
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
            env=environment,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


    def test_existing_retrieval_apis_and_lewis_memory_flows_work(self):
        lewis = Lewis()
        self.assertEqual(lewis.process("remember name is Quen"), "I'll remember that.")
        self.assertEqual(lewis.process("recall name"), "Quen")
        self.assertEqual(
            lewis.process("what is my name"),
            "Your name is Quen.",
        )
        self.assertEqual(get_memories_by_category("other")[0]["value"], "Quen")
        self.assertEqual(get_memories()[0]["key"], "name")
        self.assertEqual(memory_storage.recall("name"), "Quen")

    def test_lewis_gemini_request_and_event_log_flow_remains_wired(self):
        lewis = Lewis()
        with patch.object(
            lewis_module, "ask_ai", return_value="Gemini response"
        ) as ask_gemini, patch.object(lewis_module, "log_event") as log_event:
            self.assertEqual(lewis.process("Tell me a story"), "Gemini response")

        ask_gemini.assert_called_once()
        events = [call.args[0] for call in log_event.call_args_list]
        self.assertEqual(events[0], "AI REQUEST STARTED")
        self.assertRegex(events[1], r"^AI RESPONSE TIME: \d+ ms$")
        self.assertEqual(events[2], "AI RESPONSE RECEIVED")

    def test_named_robot_can_be_recalled_by_common_question_forms(self):
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "test robot",
            "name",
            "Copperhead",
            category="project",
        )

        self.assertEqual(
            query_memory("What is my test robot named?", project_name="ATLAS"),
            "Your test robot is named Copperhead.",
        )
        self.assertEqual(
            query_memory(
                "What is the name of my test robot?",
                project_name="ATLAS",
            ),
            "Your test robot is named Copperhead.",
        )
        self.assertEqual(
            query_memory("Do you remember my test robot?", project_name="ATLAS"),
            "Yes - your test robot is named Copperhead.",
        )
        self.assertEqual(
            query_memory(
                "What's my test robot's name?",
                project_name="ATLAS",
            ),
            "Your test robot is named Copperhead.",
        )
        with patch.object(lewis_module, "ask_ai") as ask_gemini:
            response = Lewis().process("What's my missing pet's name?")
        ask_gemini.assert_not_called()
        self.assertEqual(
            response,
            "I don't have a recorded name for missing pet.",
        )

    def test_ambiguous_partial_name_lookup_does_not_choose_a_fact(self):
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "test robot",
            "name",
            "Copperhead",
            category="project",
        )
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "delivery robot",
            "name",
            "Copper",
            category="project",
        )

        self.assertEqual(
            query_memory(
                "What is my robot named?",
                project_name="ATLAS",
            ),
            "I don't have a recorded name for robot.",
        )

    def test_main_entrypoint_captures_restarts_recalls_and_rejects_nonfacts(self):
        unavailable = ServerError(503, {"error": "temporarily unavailable"})
        with (
            patch(
                "builtins.input",
                side_effect=[
                    "1",
                    "My test robot is named Copperhead.",
                    "I'm really into robotics.",
                    "I'm tired today.",
                    "What if my fictional robot is named Imaginary?",
                    "exit",
                ],
            ),
            patch("builtins.print"),
            patch(
                "core.lewis.ask_ai",
                side_effect=unavailable,
            ) as ask_gemini,
        ):
            lewis_main.main()

        self.assertEqual(ask_gemini.call_count, 4)
        project_facts = project_memory_storage.get_project_facts("ATLAS")
        self.assertEqual(len(project_facts), 1)
        self.assertEqual(project_facts[0]["subject"], "test robot")
        self.assertEqual(project_facts[0]["value"], "Copperhead")
        personal_facts = get_memories()
        self.assertEqual(len(personal_facts), 1)
        self.assertEqual(personal_facts[0]["value"], "robotics")

        child_code = """
import sys
from pathlib import Path

from core import lewis as lewis_module
from core.lewis import Lewis
from memory import conversations, memory, project_memory
from memory.manager import get_memories

memory.MEMORY_FILE = Path(sys.argv[1])
project_memory.PROJECT_MEMORY_FILE = Path(sys.argv[2])
conversations.CONVERSATIONS_FILE = Path(sys.argv[3])

def unexpected_ai_call(message):
    raise AssertionError("A deterministic memory query called Gemini")

lewis_module.ask_ai = unexpected_ai_call
lewis = Lewis()
assert lewis.process("What is my test robot called?") == (
    "Your test robot is named Copperhead."
)
assert lewis.process("What are my interests?") == (
    "You're interested in: robotics."
)
assert lewis.process("What do you remember about my imaginary pet?") == (
    "I don't have anything recorded about imaginary pet."
)
assert len(project_memory.get_project_facts("ATLAS")) == 1
assert len(get_memories()) == 1
"""
        environment = dict(os.environ)
        project_root = str(Path(__file__).resolve().parents[1])
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(None, [project_root, environment.get("PYTHONPATH")])
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                child_code,
                str(self.memory_path),
                str(self.project_memory_path),
                str(conversations.CONVERSATIONS_FILE),
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
            env=environment,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_capture_starts_without_gemini_credentials(self):
        child_code = """
import os
import sys
from pathlib import Path

import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: None
os.environ.pop("GEMINI_API_KEY", None)

import main
from core.lewis import Lewis
from memory import conversations, memory, project_memory

memory.MEMORY_FILE = Path(sys.argv[1])
project_memory.PROJECT_MEMORY_FILE = Path(sys.argv[2])
conversations.CONVERSATIONS_FILE = Path(sys.argv[3])

lewis = Lewis()
response = lewis.process("My test robot is named Copperhead.")
assert response == lewis.MODEL_UNAVAILABLE_RESPONSE

facts = project_memory.get_project_facts("ATLAS")
assert len(facts) == 1
assert facts[0]["subject"] == "test robot"
assert facts[0]["value"] == "Copperhead"
exchange = conversations.get_conversation(lewis.active_conversation_id)
assert [message["role"] for message in exchange["messages"]] == [
    "user",
    "error",
    "assistant",
]
"""
        environment = dict(os.environ)
        environment.pop("GEMINI_API_KEY", None)
        project_root = str(Path(__file__).resolve().parents[1])
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(None, [project_root, environment.get("PYTHONPATH")])
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                child_code,
                str(self.memory_path),
                str(self.project_memory_path),
                str(Path(self.temp_dir.name) / "no-key-conversations.json"),
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
            env=environment,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_project_idea_is_not_recalled_as_a_chosen_component(self):
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "Cyberdeck",
            "project",
            "a cyberdeck, any suggestions",
        )

        response = query_memory(
            "What hardware have I explicitly chosen for my cyberdeck?"
        )

        self.assertEqual(
            response,
            "I don't have any hardware components recorded as chosen "
            "for cyberdeck.",
        )
        with patch.object(lewis_module, "ask_ai") as ask_gemini:
            response = Lewis().process(
                "What hardware have I explicitly chosen for my cyberdeck?"
            )
        ask_gemini.assert_not_called()
        self.assertEqual(
            response,
            "I don't have any hardware components recorded as chosen "
            "for cyberdeck.",
        )

    def test_explicit_project_choice_can_be_recalled(self):
        with patch.object(
            lewis_module,
            "ask_ai",
            return_value="Got it.",
        ):
            Lewis().process(
                "I chose a Raspberry Pi as a hardware component "
                "for my cyberdeck."
            )

        response = query_memory(
            "What hardware have I explicitly chosen for my cyberdeck?"
        )

        self.assertEqual(
            response,
            "You chose a Raspberry Pi for cyberdeck.",
        )

    def test_generated_prompt_separates_memory_from_suggestions(self):
        remember_memory(
            "project",
            "a cyberdeck, any suggestions",
            "project",
        )
        with patch.object(
            lewis_module,
            "ask_ai",
            return_value="I can help plan it.",
        ) as ask_gemini:
            Lewis().process("Can you help me with my cyberdeck?")

        prompt = ask_gemini.call_args.args[0]
        self.assertIn("a cyberdeck, any suggestions", prompt)
        self.assertNotIn("confirmed user decisions", prompt)
        self.assertIn("confirmed user decisions", LEWIS_IDENTITY)
        self.assertIn("Treat assistant-generated suggestions", LEWIS_IDENTITY)
        self.assertIn("no choice is recorded", LEWIS_IDENTITY)

    def test_corrupted_json_raises_without_overwriting_data(self):
        corrupted = '{"memories": ['
        self.memory_path.write_text(corrupted, encoding="utf-8")

        with self.assertRaises(memory_storage.MemoryStorageError):
            memory_storage.load_memory()
        with self.assertRaises(memory_storage.MemoryStorageError):
            memory_storage.remember("name", "Quen", "identity", 1.0)

        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), corrupted)

    def test_unreadable_file_does_not_look_like_empty_memory(self):
        self.memory_path.write_text('{"memories": []}', encoding="utf-8")
        with patch.object(Path, "open", side_effect=PermissionError("access denied")):
            with self.assertRaises(memory_storage.MemoryStorageError):
                memory_storage.load_memory()

    def test_failed_persistence_is_reported(self):
        with patch.object(
            memory_storage.os, "replace", side_effect=OSError("disk unavailable")
        ):
            with self.assertRaises(memory_storage.MemoryStorageError):
                memory_storage.remember("name", "Quen", "identity", 1.0)

        self.assertFalse(self.memory_path.exists())

    def test_failed_update_preserves_existing_memory_file(self):
        remember_memory("name", "Quen", "identity")
        original = self.memory_path.read_bytes()

        with patch.object(
            memory_storage.os,
            "replace",
            side_effect=OSError("disk unavailable"),
        ):
            with self.assertRaises(memory_storage.MemoryStorageError):
                remember_memory("name", "Updated", "identity")

        self.assertEqual(self.memory_path.read_bytes(), original)
        self.assertEqual(memory_storage.recall("name"), "Quen")

    def test_failed_project_write_preserves_existing_file(self):
        project_memory_storage.remember_project_fact(
            "ATLAS",
            "AXIS",
            "subsystem_of",
            "ATLAS",
        )
        original = self.project_memory_path.read_bytes()

        with patch.object(
            project_memory_storage.os,
            "replace",
            side_effect=OSError("disk unavailable"),
        ):
            with self.assertRaises(
                project_memory_storage.ProjectMemoryStorageError
            ):
                project_memory_storage.remember_project_fact(
                    "ATLAS",
                    "AXIS",
                    "subsystem_of",
                    "Updated",
                )

        self.assertEqual(self.project_memory_path.read_bytes(), original)

    def test_invalid_project_fact_is_rejected_before_creating_file(self):
        with self.assertRaises(ValueError):
            project_memory_storage.remember_project_fact(
                "ATLAS",
                "AXIS",
                "subsystem_of",
                "ATLAS",
                importance=float("nan"),
            )

        self.assertFalse(self.project_memory_path.exists())

    def test_corrupt_project_json_is_not_treated_as_empty_memory(self):
        corrupted = '{"projects":'
        self.project_memory_path.write_text(corrupted, encoding="utf-8")

        with self.assertRaises(
            project_memory_storage.ProjectMemoryStorageError
        ):
            project_memory_storage.get_project_facts("ATLAS")

        self.assertEqual(
            self.project_memory_path.read_text(encoding="utf-8"),
            corrupted,
        )

    def test_structured_data_is_validated_before_write(self):
        with self.assertRaises(memory_storage.MemoryStorageError):
            memory_storage.save_memory({"memories": [None]})
        self.assertFalse(self.memory_path.exists())


if __name__ == "__main__":
    unittest.main()
