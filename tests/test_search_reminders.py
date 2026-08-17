"""Tests für Gedächtnis-Suche, Intent-Prüfung und Erinnerungen."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.core.intent import sanitize_analysis
from src.memory.models import MemoryEntry
from src.memory.search import rank, resolve_single
from src.tools.reminders import ReminderStore, parse_german_time


def entry(information: str, category: str = "person") -> MemoryEntry:
    return MemoryEntry(
        id=None,
        category=category,
        memory_type="fakt",
        entity_type=None,
        information=information,
    )


class TestMemorySearch(unittest.TestCase):
    def test_ranking_prefers_best_match(self):
        entries = [
            entry("Mein Hund heißt Rex"),
            entry("Mein Auto ist blau"),
        ]

        results = rank(entries, "Wie heißt mein Hund?")

        self.assertTrue(results)
        self.assertIn("Rex", results[0].entry.information)

    def test_ignores_case_and_umlaut_spelling(self):
        results = rank([entry("Meine Schwester heißt Grüne Straße")], "gruene strasse")
        self.assertTrue(results)

    def test_ambiguous_match_is_rejected(self):
        entries = [
            entry("Mein Bruder heißt Tim"),
            entry("Mein Bruder heißt Tom"),
        ]

        result = resolve_single(entries, "Mein Bruder heißt")

        self.assertIsNone(result.best)
        self.assertTrue(result.ambiguous)


class TestIntentSanitizing(unittest.TestCase):
    def test_unknown_tool_is_discarded(self):
        analysis = sanitize_analysis(
            {"action": "KEINE", "tool": "raketenstart", "tool_arguments": {}},
            known_tools=["calculator"],
        )

        self.assertEqual(analysis["tool"], "")

    def test_known_tool_is_kept(self):
        analysis = sanitize_analysis(
            {"action": "KEINE", "tool": "calculator", "tool_arguments": {"expression": "1+1"}},
            known_tools=["calculator"],
        )

        self.assertEqual(analysis["tool"], "calculator")
        self.assertEqual(analysis["tool_arguments"], {"expression": "1+1"})

    def test_invalid_action_falls_back(self):
        analysis = sanitize_analysis({"action": "QUATSCH"}, known_tools=[])
        self.assertEqual(analysis["action"], "KEINE")


class TestReminders(unittest.TestCase):
    def test_relative_time(self):
        reference = datetime(2026, 8, 17, 20, 0)
        due = parse_german_time("in 10 minuten", reference=reference)

        self.assertEqual(due, reference + timedelta(minutes=10))

    def test_tomorrow_with_hour(self):
        reference = datetime(2026, 8, 17, 20, 0)
        due = parse_german_time("morgen um 8", reference=reference)

        self.assertEqual(due, datetime(2026, 8, 18, 8, 0))

    def test_unparsable_time(self):
        self.assertIsNone(parse_german_time("irgendwann später"))

    def test_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ReminderStore(Path(folder) / "reminders.db")

            reminder = store.add("Ofen prüfen", datetime(2026, 8, 17, 21, 0))
            self.assertEqual(len(store.list()), 1)
            self.assertEqual(len(store.due(datetime(2026, 8, 17, 22, 0))), 1)

            self.assertTrue(store.complete(reminder.id))
            self.assertEqual(store.list(), [])


if __name__ == "__main__":
    unittest.main()
