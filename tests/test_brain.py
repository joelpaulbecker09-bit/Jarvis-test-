import unittest
from unittest.mock import MagicMock
from pathlib import Path
import tempfile
import json

from src.core.brain import JarvisBrain
from src.llm.model_manager import ModelManager


class TestJarvisBrain(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_brain_memory.db"
        
        self.mock_model_manager = MagicMock(spec=ModelManager)
        
        # Patch config db path temporarily for tests
        import config.config as cfg
        self.original_db_path = cfg.config._settings["db_name"]
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_analyze_message_sanitization(self):
        brain = JarvisBrain(model_manager=self.mock_model_manager)
        
        mock_analysis_json = json.dumps({
            "action": "NEU",
            "search_target": "",
            "category": "Musik",
            "memory_type": "Vorliebe",
            "entity_type": "Band",
            "information": "Deftones",
            "time_context": "seit 2022",
            "memory_scope": "KEINE"
        })
        self.mock_model_manager.chat.return_value = mock_analysis_json
        
        analysis = brain.analyze_message("Ich mag Deftones seit 2022.")
        self.assertEqual(analysis["action"], "NEU")
        self.assertEqual(analysis["category"], "Musik")
        self.assertEqual(analysis["information"], "Deftones")
        self.assertEqual(analysis["time_context"], "seit 2022")

    def test_respond_cycle(self):
        brain = JarvisBrain(model_manager=self.mock_model_manager)
        
        analysis_json = json.dumps({
            "action": "KEINE",
            "search_target": "",
            "category": "",
            "memory_type": "",
            "entity_type": "",
            "information": "",
            "time_context": None,
            "memory_scope": "KEINE"
        })
        self.mock_model_manager.chat.side_effect = [
            analysis_json,  # for analyze_message
            "Sehr wohl, Sir. Ich bin bereit."  # for generate_response
        ]
        
        response = brain.respond("Hallo JARVIS")
        self.assertIn("Sir", response)
        self.assertEqual(len(brain.conversation_history), 2)


if __name__ == "__main__":
    unittest.main()
