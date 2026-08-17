import unittest
from pathlib import Path
import tempfile
import os

from src.memory.memory import Memory


class TestMemorySystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_memory.db"
        self.memory = Memory(database_path=self.db_path)

    def tearDown(self):
        self.memory.close()
        self.temp_dir.cleanup()

    def test_save_and_retrieve(self):
        saved = self.memory.save(
            category="Musik",
            memory_type="Vorliebe",
            entity_type="Band",
            information="Deftones",
            time_context="seit 2022"
        )
        self.assertTrue(saved)
        self.assertEqual(self.memory.count(), 1)

        memories = self.memory.get_by_category("Musik")
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0][3], "Deftones")
        self.assertEqual(memories[0][4], "seit 2022")

    def test_duplicate_prevention(self):
        self.memory.save(
            category="Musik",
            memory_type="Vorliebe",
            entity_type="Band",
            information="Deftones"
        )
        # Duplicate attempt
        second_save = self.memory.save(
            category="Musik",
            memory_type="Vorliebe",
            entity_type="Band",
            information="Deftones"
        )
        self.assertFalse(second_save)
        self.assertEqual(self.memory.count(), 1)

    def test_update_memory(self):
        self.memory.save(
            category="Musik",
            memory_type="Vorliebe",
            entity_type="Band",
            information="Linkin Park"
        )
        existing = self.memory.find_by_information("Linkin Park")
        self.assertIsNotNone(existing)

        memory_id = existing[0]
        updated = self.memory.update(
            memory_id=memory_id,
            category="Musik",
            memory_type="Abneigung",
            entity_type="Band",
            information="Linkin Park"
        )
        self.assertTrue(updated)

        updated_entry = self.memory.get_by_id(memory_id)
        self.assertEqual(updated_entry[2], "Abneigung")

    def test_delete_memory(self):
        self.memory.save(
            category="Hobbys",
            memory_type="Vorliebe",
            entity_type="Hobby",
            information="Schlagzeug"
        )
        self.assertEqual(self.memory.count(), 1)

        existing = self.memory.find_by_information("Schlagzeug")
        deleted = self.memory.delete(existing[0])
        self.assertTrue(deleted)
        self.assertEqual(self.memory.count(), 0)


if __name__ == "__main__":
    unittest.main()
