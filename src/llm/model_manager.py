"""
JARVIS LLM Model Manager

Zentraler Verwalter für LLM-Aufrufe, Modellwahl und Fallbacks.
"""

from typing import Any, Dict, List, Optional

from config.config import config
from config.models import DEFAULT_TASK_MODELS, TaskType
from src.llm.base import LLMProvider
from src.llm.ollama_provider import OllamaProvider
from src.utils.logging import LLM, get_logger

logger = get_logger(LLM)


class ModelManager:
    """
    ModelManager entkoppelt das Gehirn von spezifischen LLM-Providern.
    Ermöglicht dynamischen Modellwechsel je nach Aufgabe.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or OllamaProvider()
        self.default_model = config.default_model

    def get_model_for_task(self, task_type: TaskType) -> str:
        """
        Ermittelt das passende Modell für einen bestimmten Task-Typ.
        """
        return DEFAULT_TASK_MODELS.get(task_type, self.default_model)

    def is_available(self) -> bool:
        """
        Prüft, ob der Provider erreichbar ist. Fehlt die Prüfung, gilt der
        Provider als verfügbar (relevant für Test-Doubles).
        """
        checker = getattr(self.provider, "is_available", None)

        if checker is None:
            return True

        try:
            return bool(checker())
        except Exception as error:
            logger.warning(f"Verfügbarkeitsprüfung fehlgeschlagen: {error}")
            return False

    def available_models(self) -> List[str]:
        lister = getattr(self.provider, "list_models", None)

        if lister is None:
            return []

        try:
            return list(lister())
        except Exception:
            return []

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        task_type: TaskType = TaskType.CHAT,
        json_mode: bool = False,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Verarbeitet eine Chat-Anfrage mit dem ausgewählten Modell.
        """
        selected_model = model or self.get_model_for_task(task_type)

        try:
            return self.provider.chat(
                model=selected_model,
                messages=messages,
                json_mode=json_mode,
                options=options
            )
        except Exception as err:
            # Fallback auf Default-Modell, falls ein spezifisches Modell fehlschlägt
            if selected_model != self.default_model:
                logger.warning(
                    f"Fallback von {selected_model} auf {self.default_model}"
                )
                return self.provider.chat(
                    model=self.default_model,
                    messages=messages,
                    json_mode=json_mode,
                    options=options
                )
            raise err
