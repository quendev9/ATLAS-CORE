
import unittest
from unittest.mock import call, patch

from memory.manager import extract_facts, process_memory


class MemoryExtractionTests(unittest.TestCase):

    def test_named_entity_and_pronoun_relationship(self):
        facts = extract_facts(
            "The robotic arm will be called AXIS. "
            "It will be a subsystem of ATLAS."
        )

        self.assertEqual(len(facts), 2)

        self.assertEqual(
            facts[0]["subject"],
            "robotic arm",
        )
        self.assertEqual(facts[0]["predicate"], "name")
        self.assertEqual(facts[0]["value"], "AXIS")

        self.assertEqual(facts[1]["subject"], "AXIS")
        self.assertEqual(facts[1]["predicate"], "subsystem_of")
        self.assertEqual(facts[1]["value"], "ATLAS")

    def test_unresolved_pronoun_is_not_saved_as_entity(self):
        facts = extract_facts(
            "It will be a subsystem of ATLAS."
        )

        self.assertEqual(facts, [])

    def test_explicit_relationship_is_preserved(self):
        facts = extract_facts(
            "AXIS is a subsystem of ATLAS."
        )

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["subject"], "AXIS")
        self.assertEqual(facts[0]["predicate"], "subsystem_of")
        self.assertEqual(facts[0]["value"], "ATLAS")

    def test_process_memory_routes_project_facts_to_project_storage(self):
        with patch("memory.manager.remember_project_fact") as save:
            save.side_effect = [
                {"subject": "robotic arm", "predicate": "name", "value": "AXIS"},
                {"subject": "AXIS", "predicate": "subsystem_of", "value": "ATLAS"},
            ]

            result = process_memory(
                "The robotic arm will be called AXIS. "
                "It will be a subsystem of ATLAS.",
                project_name="ATLAS",
            )

        self.assertEqual(len(result), 2)
        self.assertEqual(
            save.call_args_list,
            [
                call(
                    "ATLAS",
                    "robotic arm",
                    "name",
                    "AXIS",
                    category="project",
                    importance=0.9,
                    status="plan",
                ),
                call(
                    "ATLAS",
                    "AXIS",
                    "subsystem_of",
                    "ATLAS",
                    category="relationship",
                    importance=0.5,
                    status="stated",
                ),
            ],
        )

    def test_personal_memory_still_uses_user_as_subject(self):
        with patch("memory.manager.remember_memory") as save:
            save.return_value = {
                "subject": "user",
                "key": "favorite color",
                "value": "blue",
            }

            result = process_memory("My favorite color is blue.")

        self.assertEqual(result["subject"], "user")
        save.assert_called_once_with(
            "favorite color",
            "blue",
            category="preference",
            importance=0.8,
            subject="user",
            status="preference",
        )

    def test_temporary_statement_is_not_stored(self):
        with patch("memory.manager.remember_memory") as save:
            result = process_memory("I'm tired today.")

        self.assertIsNone(result)
        save.assert_not_called()

    def test_named_entity_variants_are_extracted(self):
        facts = extract_facts("My test robot is named Copperhead.")

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["subject"], "test robot")
        self.assertEqual(facts[0]["predicate"], "name")
        self.assertEqual(facts[0]["value"], "Copperhead")
        self.assertEqual(facts[0]["category"], "project")

    def test_explicit_project_choice_is_distinguished_from_idea(self):
        choice = extract_facts(
            "I chose a Raspberry Pi as a hardware component "
            "for my cyberdeck."
        )
        suggestion_request = extract_facts(
            "I'm considering a Raspberry Pi for my cyberdeck."
        )

        self.assertEqual(len(choice), 1)
        self.assertEqual(choice[0]["subject"], "cyberdeck")
        self.assertEqual(choice[0]["predicate"], "chosen_component")
        self.assertEqual(choice[0]["value"], "a Raspberry Pi")
        self.assertEqual(choice[0]["category"], "decision")
        self.assertFalse(
            any(fact.get("predicate") == "chosen_component"
                for fact in suggestion_request)
        )
        unqualified_choice = extract_facts(
            "I chose a color for my cyberdeck."
        )
        self.assertEqual(
            unqualified_choice[0]["predicate"],
            "chosen_option",
        )

    def test_plan_idea_and_decision_have_distinct_status(self):
        plan = extract_facts(
            "I'm planning to build a cyberdeck."
        )
        idea = extract_facts(
            "I'm considering a Raspberry Pi for my cyberdeck."
        )
        decision = extract_facts(
            "I chose a Raspberry Pi as a hardware component "
            "for my cyberdeck."
        )

        self.assertEqual(plan[0]["status"], "plan")
        self.assertEqual(idea[0]["status"], "idea")
        self.assertEqual(idea[0]["category"], "idea")
        self.assertEqual(decision[0]["status"], "decision")
        self.assertEqual(
            extract_facts("I finished building the robotic arm.")[0]["status"],
            "completed",
        )

    def test_questions_and_hypotheticals_are_not_extracted_as_facts(self):
        for statement in (
            "Is my favorite color blue?",
            "My favorite color is blue?",
            "What if I chose a Raspberry Pi for my cyberdeck?",
            "If I choose a Raspberry Pi for my cyberdeck, would it work?",
        ):
            with self.subTest(statement=statement):
                self.assertEqual(extract_facts(statement), [])

    def test_correction_prefix_preserves_corrected_fact(self):
        facts = extract_facts(
            "Actually, my favorite color is green."
        )

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["key"], "favorite color")
        self.assertEqual(facts[0]["value"], "green")

    def test_into_phrasings_are_extracted_as_interests(self):
        for statement in (
            "I'm into robotics.",
            "Im really into robotics!",
            "I am into robotics.",
        ):
            with self.subTest(statement=statement):
                facts = extract_facts(statement)
                self.assertEqual(len(facts), 1)
                self.assertEqual(facts[0]["category"], "interest")
                self.assertEqual(facts[0]["value"], "robotics")

    def test_multiple_first_person_facts_in_one_sentence_stay_separate(self):
        facts = extract_facts(
            "My favorite color is blue and I love robotics."
        )

        self.assertEqual(
            [(fact["key"], fact["value"]) for fact in facts],
            [("favorite color", "blue"), ("loves", "robotics")],
        )

    def test_possessive_entity_name_phrasing_is_extracted(self):
        facts = extract_facts("My robot's name is Copperhead.")

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["subject"], "robot")
        self.assertEqual(facts[0]["predicate"], "name")
        self.assertEqual(facts[0]["value"], "Copperhead")

    def test_fictional_and_quoted_statements_are_not_extracted(self):
        for statement in (
            "My fictional robot is named Copperhead.",
            "My imaginary robot is named Copperhead.",
            "In my story, my robot is named Copperhead.",
            "My test robot in my novel is named Copperhead.",
            '"My favorite color is blue."',
        ):
            with self.subTest(statement=statement):
                self.assertEqual(extract_facts(statement), [])


if __name__ == "__main__":
    unittest.main()