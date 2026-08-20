import unittest
from unittest.mock import MagicMock
from src.llm.model_manager import ModelManager
from src.llm.ollama_provider import OllamaProvider
from config.models import TaskType


class TestLLMSystem(unittest.TestCase):

    def test_model_manager_fallback(self):
        mock_provider = MagicMock(spec=OllamaProvider)
        # Force failure on specific model
        def chat_side_effect(model, messages, json_mode=False, options=None):
            if model == "gemma4:latest":
                raise ConnectionError("Model failed")
            return "Fallback answer"

        mock_provider.chat.side_effect = chat_side_effect
        manager = ModelManager(provider=mock_provider)

        result = manager.chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="gemma4:latest"
        )
        self.assertEqual(result, "Fallback answer")
        self.assertEqual(mock_provider.chat.call_count, 2)


if __name__ == "__main__":
    unittest.main()
