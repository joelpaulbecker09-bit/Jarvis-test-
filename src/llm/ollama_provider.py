"""
JARVIS LLM Provider – Ollama

Abstraktion der Ollama-Kommunikation.
Kapselt direkte API-Aufrufe an das lokale Ollama-Modell.
"""

from typing import Any, Dict, List, Optional

try:  # Ollama ist zur Laufzeit nötig, aber nicht zum Import der übrigen Module.
    import ollama
except ImportError:  # pragma: no cover - abhängig von der Installation
    ollama = None

from config.config import config
from src.llm.base import LLMError
from src.utils.logging import LLM, get_logger

logger = get_logger(LLM)


class OllamaProvider:
    """
    Schnittstelle für den Zugriff auf den lokalen Ollama-Dienst.
    """

    def __init__(self, host: Optional[str] = None):
        self.host = host or config.ollama_host

        if ollama is None:
            logger.warning(
                "Das Paket 'ollama' ist nicht installiert (pip install ollama)."
            )
            self._client = None
        else:
            self._client = ollama.Client(host=self.host)

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Führt einen Chat-Aufruf an ein Ollama-Modell aus.

        Args:
            model: Name des Ollama-Modells (z.B. 'qwen3:8b')
            messages: Liste von Nachricht-Dictionaries [{'role': 'user', 'content': '...'}]
            json_mode: Wenn True, erzwingt Ollama JSON-Format
            options: Zusätzliche Modell-Parameter (Temperatur, Top-P, etc.)

        Returns:
            Der Text-Inhalt der Antwort.
        """
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        if json_mode:
            kwargs["format"] = "json"

        if options:
            kwargs["options"] = options

        if self._client is None:
            raise LLMError(
                "Das Paket 'ollama' fehlt. Installation: pip install ollama"
            )

        try:
            response = self._client.chat(**kwargs)
            content = response.get("message", {}).get("content", "")
            return content.strip()
        except Exception as error:
            logger.error(f"Ollama-Aufruf fehlgeschlagen (Modell {model}): {error}")
            raise LLMError(f"Ollama-Kommunikationsfehler: {error}") from error

    def is_available(self) -> bool:
        """
        Prüft, ob der lokale Ollama-Dienst erreichbar ist.
        """
        if self._client is None:
            return False

        try:
            self._client.list()
            return True
        except Exception as error:
            logger.warning(f"Ollama unter {self.host} nicht erreichbar: {error}")
            return False

    def list_models(self) -> List[str]:
        """
        Liefert die lokal installierten Modellnamen.
        """
        if self._client is None:
            return []

        try:
            response = self._client.list()
        except Exception as error:
            logger.warning(f"Modellliste nicht abrufbar: {error}")
            return []

        names: List[str] = []

        for entry in response.get("models", []):
            name = entry.get("model") or entry.get("name")
            if name:
                names.append(name)

        return names
