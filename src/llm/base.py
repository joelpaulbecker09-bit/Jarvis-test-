"""
JARVIS LLM Base

Schnittstelle, die jeder LLM-Provider erfüllen muss.
Der Rest von JARVIS kennt ausschließlich diese Schnittstelle,
niemals eine konkrete Bibliothek.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class LLMError(ConnectionError):
    """Fehler bei der Kommunikation mit einem Sprachmodell."""


@runtime_checkable
class LLMProvider(Protocol):
    """Minimale Schnittstelle eines Sprachmodell-Anbieters."""

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Führt eine Chat-Anfrage aus und liefert den Antworttext."""
        ...

    def is_available(self) -> bool:
        """Prüft, ob der Anbieter gerade erreichbar ist."""
        ...

    def list_models(self) -> List[str]:
        """Listet die verfügbaren Modellnamen."""
        ...
