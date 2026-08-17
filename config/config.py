"""
JARVIS Central Configuration Module

Lädt Einstellungen aus settings.json oder nutzt Standard-Fallbacks.
"""

import json
from pathlib import Path
from typing import Any, Dict


class Config:
    """
    Zentrale Konfigurationsklasse für JARVIS.
    """

    BASE_DIR = Path(__file__).resolve().parent.parent
    CONFIG_FILE = BASE_DIR / "config" / "settings.json"

    def __init__(self):
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        defaults = {
            "default_model": "qwen3:8b",
            "fast_model": "gemma:2b",
            "reasoning_model": "gemma4:latest",
            "vision_model": "qwen3-vl:latest",
            "ollama_host": "http://localhost:11434",
            "max_history_messages": 10,
            "data_dir": "data",
            "db_name": "memory.db",
        }

        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    file_settings = json.load(f)
                    defaults.update(file_settings)
            except Exception as e:
                print(f"[WARNING] Konnte settings.json nicht laden ({e}), nutze Defaults.")

        return defaults

    @property
    def default_model(self) -> str:
        return self._settings.get("default_model", "qwen3:8b")

    @property
    def max_history_messages(self) -> int:
        return int(self._settings.get("max_history_messages", 10))

    @property
    def data_dir(self) -> Path:
        path = self.BASE_DIR / self._settings.get("data_dir", "data")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def memory_db_path(self) -> Path:
        return self.data_dir / self._settings.get("db_name", "memory.db")

    @property
    def ollama_host(self) -> str:
        return self._settings.get("ollama_host", "http://localhost:11434")

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)


config = Config()
