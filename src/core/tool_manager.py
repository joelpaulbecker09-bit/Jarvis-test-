"""
JARVIS Tool-Manager

Verbindet die Analyse mit der Tool-Registry:

    Analyse → ToolManager → Registry → PermissionPolicy → Tool

Der Manager fängt jeden Fehler ab. Ein defektes Werkzeug führt zu einer
sachlichen Rückmeldung, niemals zum Absturz von JARVIS.
"""

from typing import Any, Dict, Optional

from src.tools.base import ToolResult
from src.tools.registry import ToolRegistry
from src.utils.logging import TOOL, get_logger

logger = get_logger(TOOL)


class ToolManager:
    """Führt das vom Analyzer gewählte Werkzeug aus."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()
        self.last_result: Optional[ToolResult] = None
        self.last_tool: str = ""

    @property
    def descriptions(self) -> str:
        return self.registry.describe()

    @property
    def names(self) -> list:
        return self.registry.names()

    def run_from_analysis(self, analysis: Dict[str, Any]) -> Optional[ToolResult]:
        """
        Führt das in der Analyse genannte Werkzeug aus.
        Gibt None zurück, wenn kein Werkzeug gefordert war.
        """
        name = str(analysis.get("tool") or "").strip()

        if not name:
            self.last_result = None
            self.last_tool = ""
            return None

        arguments = analysis.get("tool_arguments")
        arguments = dict(arguments) if isinstance(arguments, dict) else {}

        result = self.registry.execute(name, arguments)

        self.last_tool = name
        self.last_result = result

        return result

    @staticmethod
    def result_text(name: str, result: ToolResult) -> str:
        """Formulierung für den Antwort-Prompt."""
        if result.ok:
            return result.output

        return (
            f"Das Werkzeug {name} war nicht erfolgreich: "
            f"{result.error or 'unbekannter Fehler'}"
        )
