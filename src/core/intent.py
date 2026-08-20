"""
JARVIS Intent-Analyse

Ein einziger LLM-Aufruf ermittelt:

    Memory-Aktion · Memory-Bereich · benötigtes Werkzeug

Das Ergebnis wird streng validiert: unbekannte Kategorien, Aktionen oder
Werkzeuge werden verworfen, damit das Modell nichts erfinden kann.
"""

import json
from typing import Any, Dict, List, Optional, Sequence

from config.models import TaskType
from src.llm.model_manager import ModelManager
from src.llm.prompts import build_analyzer_prompt
from src.memory import models
from src.utils.logging import CORE, get_logger

logger = get_logger(CORE)

CATEGORIES = set(models.CATEGORIES)
MEMORY_TYPES = set(models.MEMORY_TYPES)
ENTITY_TYPES = set(models.ENTITY_TYPES)
MEMORY_ACTIONS = set(models.MEMORY_ACTIONS)
MEMORY_SCOPES = set(models.MEMORY_SCOPES)


def empty_analysis() -> Dict[str, Any]:
    return {
        "action": "KEINE",
        "search_target": "",
        "category": "",
        "memory_type": "",
        "entity_type": "",
        "information": "",
        "time_context": None,
        "memory_scope": "KEINE",
        "tool": "",
        "tool_arguments": {},
    }


def sanitize_analysis(
    analysis: Dict[str, Any],
    known_tools: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Bringt eine Modellantwort auf eine sichere, vollständige Struktur.
    """
    action = str(analysis.get("action", "KEINE")).upper().strip()
    if action not in MEMORY_ACTIONS:
        action = "KEINE"

    category = str(analysis.get("category", "")).strip()
    if category not in CATEGORIES:
        category = ""

    memory_type = str(analysis.get("memory_type", "")).strip()
    if memory_type not in MEMORY_TYPES:
        memory_type = ""

    entity_type = str(analysis.get("entity_type", "")).strip()
    if entity_type not in ENTITY_TYPES:
        entity_type = ""

    information = str(analysis.get("information", "")).strip()
    search_target = str(analysis.get("search_target", "")).strip()

    time_context = analysis.get("time_context")
    if time_context is not None:
        time_context = str(time_context).strip() or None

    scope = str(analysis.get("memory_scope", "KEINE")).strip()
    if scope not in MEMORY_SCOPES:
        scope = "KEINE"

    tool = str(analysis.get("tool") or "").strip()
    if known_tools is not None and tool not in set(known_tools):
        if tool:
            logger.warning(f"Unbekanntes Werkzeug verworfen: {tool}")
        tool = ""

    raw_arguments = analysis.get("tool_arguments")
    tool_arguments: Dict[str, Any] = (
        dict(raw_arguments) if isinstance(raw_arguments, dict) else {}
    )

    if not tool:
        tool_arguments = {}

    # Sicherheitsregel: KEINE darf keine Memory-Daten auslösen.
    if action == "KEINE":
        category = ""
        memory_type = ""
        entity_type = ""
        information = ""
        time_context = None

    if action == "NEU" and not (category and memory_type and information):
        action = "KEINE"

    if action in {"AENDERN", "LOESCHEN"} and not search_target:
        action = "KEINE"

    return {
        "action": action,
        "search_target": search_target,
        "category": category,
        "memory_type": memory_type,
        "entity_type": entity_type,
        "information": information,
        "time_context": time_context,
        "memory_scope": scope,
        "tool": tool,
        "tool_arguments": tool_arguments,
    }


class IntentAnalyzer:
    """Analysiert eine Nachricht mit genau einem LLM-Aufruf."""

    def __init__(
        self,
        model_manager: ModelManager,
        tool_descriptions: str = "",
        known_tools: Optional[List[str]] = None,
    ):
        self.model_manager = model_manager
        self.tool_descriptions = tool_descriptions
        self.known_tools = known_tools

    def analyze(self, message: str) -> Dict[str, Any]:
        try:
            content = self.model_manager.chat(
                messages=[
                    {
                        "role": "system",
                        "content": build_analyzer_prompt(self.tool_descriptions),
                    },
                    {"role": "user", "content": message},
                ],
                task_type=TaskType.ANALYSIS,
                json_mode=True,
            )
            parsed = json.loads(content)
        except (json.JSONDecodeError, ValueError) as error:
            logger.error(f"Analyse nicht lesbar: {error}")
            return empty_analysis()
        except Exception as error:
            logger.error(f"Analyse fehlgeschlagen: {error}")
            return empty_analysis()

        if not isinstance(parsed, dict):
            return empty_analysis()

        return sanitize_analysis(parsed, self.known_tools)
