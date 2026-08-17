"""
JARVIS LLM Provider – Ollama

Abstraktion der Ollama-Kommunikation.
Kapselt direkte API-Aufrufe an das lokale Ollama-Modell.
"""

from typing import List, Dict, Any, Optional
import ollama
from config.config import config


class OllamaProvider:
    """
    Schnittstelle für den Zugriff auf den lokalen Ollama-Dienst.
    """

    def __init__(self, host: Optional[str] = None):
        self.host = host or config.ollama_host

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
        kwargs = {
            "model": model,
            "messages": messages,
        }

        if json_mode:
            kwargs["format"] = "json"

        if options:
            kwargs["options"] = options

        try:
            response = ollama.chat(**kwargs)
            content = response.get("message", {}).get("content", "")
            return content.strip()
        except Exception as error:
            print(f"[LLM ERROR] Ollama-Aufruf fehlgeschlagen (Modell {model}): {error}")
            raise ConnectionError(f"Ollama-Kommunikationsfehler: {error}") from error
