"""
JARVIS Conversation Context

Verwaltet das Kurzzeitgedächtnis (Gesprächsverlauf) während einer Sitzung.
"""

from typing import List, Dict, Any, Optional
from config.config import config


class ConversationContext:
    """
    Verwaltet die flüchtige Gesprächshistorie.
    """

    def __init__(self, max_history: Optional[int] = None):
        self.max_history = max_history or config.max_history_messages
        self._history: List[Dict[str, str]] = []

    def add_user_message(self, content: str) -> None:
        """
        Fügt eine Benutzer-Nachricht hinzu.
        """
        self._history.append({"role": "user", "content": content.strip()})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        """
        Fügt eine Assistenten-Antwort hinzu.
        """
        self._history.append({"role": "assistant", "content": content.strip()})
        self._trim()

    def get_recent_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Gibt die letzten Nachrichten bis zum Limit zurück.
        """
        limit = limit or self.max_history
        return self._history[-limit:]

    def get_all_history(self) -> List[Dict[str, str]]:
        """
        Gibt die gesamte Historie der aktuellen Sitzung zurück.
        """
        return list(self._history)

    def clear(self) -> None:
        """
        Löscht den bisherigen Verlauf.
        """
        self._history.clear()

    def _trim(self) -> None:
        """
        Begrenzt die Historie auf max_history Einträge.
        """
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
