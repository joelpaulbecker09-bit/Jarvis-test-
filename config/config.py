"""
JARVIS Central Configuration Module

Lädt Einstellungen aus settings.json (optional überschrieben durch .env)
oder nutzt Standard-Fallbacks.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


DEFAULT_SETTINGS: Dict[str, Any] = {
    "default_model": "qwen3:8b",
    "fast_model": "gemma:2b",
    "reasoning_model": "gemma4:latest",
    "vision_model": "qwen3-vl:latest",
    "ollama_host": "http://localhost:11434",
    "max_history_messages": 10,
    "data_dir": "data",
    "db_name": "memory.db",
    "user_name": "Joel",
    "language": "de",
    "logging": {
        "level": "INFO",
        "to_file": False,
        "file_name": "jarvis.log",
    },
    "voice": {
        "tts_enabled": True,
        "tts_engine": "auto",
        "piper_model": "",
        "voice_rate": 165,
        "stt_enabled": True,
        "stt_engine": "auto",
        "whisper_model": "base",
        "vosk_model": "",
        "wake_word": "jarvis",
        "sample_rate": 16000,
        "max_record_seconds": 30,
    },
    "ui": {
        "enabled": True,
        "window_width": 900,
        "window_height": 640,
        "particle_count": 500,
        "target_fps": 60,
        "accent_color": "#5ad0ff",
    },
    "tools": {
        "enabled": True,
        "allow_terminal": False,
        "allow_file_write": True,
        "allow_file_delete": False,
        "confirm_dangerous": True,
        "file_roots": [],
        "terminal_timeout": 20,
    },
    "web": {
        "enabled": True,
        "provider_order": [
            "duckduckgo_html",
            "duckduckgo_lite",
            "duckduckgo_api",
            "wikipedia",
        ],
        "max_results": 5,
        "timeout": 10,
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Führt verschachtelte Dictionaries zusammen, ohne Untersektionen zu verlieren."""
    result = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


class Config:
    """
    Zentrale Konfigurationsklasse für JARVIS.
    """

    BASE_DIR = Path(__file__).resolve().parent.parent
    CONFIG_FILE = BASE_DIR / "config" / "settings.json"
    ENV_FILE = BASE_DIR / ".env"

    def __init__(self):
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        settings = _deep_merge({}, DEFAULT_SETTINGS)

        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    settings = _deep_merge(settings, json.load(f))
            except Exception as e:
                print(f"[WARNUNG] Konnte settings.json nicht laden ({e}), nutze Defaults.")

        return _deep_merge(settings, self._load_env_overrides())

    def _load_env_overrides(self) -> Dict[str, Any]:
        """
        Liest einfache Überschreibungen aus .env bzw. den Umgebungsvariablen.

        Unterstützt:
            JARVIS_MODEL, JARVIS_OLLAMA_HOST, JARVIS_USER_NAME, JARVIS_LOG_LEVEL
        """
        values: Dict[str, str] = {}

        if self.ENV_FILE.exists():
            try:
                for raw_line in self.ENV_FILE.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip().strip('"').strip("'")
            except Exception as e:
                print(f"[WARNUNG] Konnte .env nicht laden ({e}).")

        values.update(
            {
                key: value
                for key, value in os.environ.items()
                if key.startswith("JARVIS_")
            }
        )

        overrides: Dict[str, Any] = {}

        if values.get("JARVIS_MODEL"):
            overrides["default_model"] = values["JARVIS_MODEL"]

        if values.get("JARVIS_OLLAMA_HOST"):
            overrides["ollama_host"] = values["JARVIS_OLLAMA_HOST"]

        if values.get("JARVIS_USER_NAME"):
            overrides["user_name"] = values["JARVIS_USER_NAME"]

        if values.get("JARVIS_LOG_LEVEL"):
            overrides["logging"] = {"level": values["JARVIS_LOG_LEVEL"]}

        return overrides

    @property
    def default_model(self) -> str:
        return self._settings.get("default_model", "qwen3:8b")

    @property
    def max_history_messages(self) -> int:
        return int(self._settings.get("max_history_messages", 10))

    @property
    def user_name(self) -> str:
        return self._settings.get("user_name", "Joel")

    @property
    def language(self) -> str:
        return self._settings.get("language", "de")

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

    @property
    def log_file_path(self) -> Path:
        return self.BASE_DIR / "logs" / self.section("logging").get("file_name", "jarvis.log")

    def section(self, name: str) -> Dict[str, Any]:
        """
        Liefert eine Konfigurationssektion (voice, ui, tools, web, logging).
        """
        value = self._settings.get(name, {})
        return dict(value) if isinstance(value, dict) else {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)


config = Config()
