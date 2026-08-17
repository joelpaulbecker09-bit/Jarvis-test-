"""
JARVIS Tool-Registry

Zentrale Stelle, an der JARVIS weiß, welche Werkzeuge es gibt.

    Anfrage → Registry.execute → PermissionPolicy → Tool.execute → ToolResult

Ein Fehler in einem Tool beendet JARVIS nie: er wird protokolliert und als
ToolResult mit ok=False zurückgegeben.
"""

from typing import Dict, List, Optional

from src.tools.applications import (
    CloseApplicationTool,
    OpenApplicationTool,
    RunningApplicationsTool,
)
from src.tools.base import Tool, ToolResult
from src.tools.calculator import CalculatorTool
from src.tools.files import (
    CopyFileTool,
    DeleteFileTool,
    FindFileTool,
    ListDirectoryTool,
    MoveFileTool,
    ReadFileTool,
    WriteFileTool,
)
from src.tools.permissions import ConfirmHandler, PermissionPolicy
from src.tools.reminders import (
    AddReminderTool,
    CompleteReminderTool,
    DeleteReminderTool,
    ListRemindersTool,
    ReminderStore,
)
from src.tools.system import DiskSpaceTool, SystemInfoTool, VolumeTool
from src.tools.terminal import TerminalTool
from src.tools.time_tools import CurrentTimeTool
from src.tools.web import FetchUrlTool, WebSearchTool
from src.utils.logging import TOOL, get_logger

logger = get_logger(TOOL)


class ToolRegistry:
    """Verwaltet alle verfügbaren Tools und führt sie abgesichert aus."""

    def __init__(
        self,
        policy: Optional[PermissionPolicy] = None,
        confirm_handler: Optional[ConfirmHandler] = None,
        register_defaults: bool = True,
    ):
        self.policy = policy or PermissionPolicy(confirm_handler=confirm_handler)
        self._tools: Dict[str, Tool] = {}

        if register_defaults:
            self.register_defaults()

    # ------------------------------------------------------------
    # Registrierung
    # ------------------------------------------------------------

    def register(self, tool: Tool) -> bool:
        """Nimmt ein Tool auf, sofern es auf diesem System nutzbar ist."""
        if not tool.name:
            logger.warning("Tool ohne Namen wird ignoriert.")
            return False

        if not tool.is_available():
            logger.info(f"Tool nicht verfügbar und übersprungen: {tool.name}")
            return False

        self._tools[tool.name] = tool
        return True

    def register_defaults(self) -> None:
        store = ReminderStore()

        tools: List[Tool] = [
            CurrentTimeTool(),
            CalculatorTool(),
            SystemInfoTool(),
            DiskSpaceTool(),
            VolumeTool(),
            WebSearchTool(),
            FetchUrlTool(),
            ListDirectoryTool(self.policy),
            FindFileTool(self.policy),
            ReadFileTool(self.policy),
            WriteFileTool(self.policy),
            MoveFileTool(self.policy),
            CopyFileTool(self.policy),
            DeleteFileTool(self.policy),
            OpenApplicationTool(),
            CloseApplicationTool(),
            RunningApplicationsTool(),
            TerminalTool(self.policy),
            AddReminderTool(store),
            ListRemindersTool(store),
            CompleteReminderTool(store),
            DeleteReminderTool(store),
        ]

        for tool in tools:
            self.register(tool)

        logger.info(f"{len(self._tools)} Tools registriert.")

    # ------------------------------------------------------------
    # Zugriff
    # ------------------------------------------------------------

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return sorted(self._tools)

    def all(self) -> List[Tool]:
        return [self._tools[name] for name in self.names()]

    def describe(self) -> str:
        """Beschreibung aller Tools für den Auswahl-Prompt des LLM."""
        return "\n".join(tool.describe() for tool in self.all())

    # ------------------------------------------------------------
    # Ausführung
    # ------------------------------------------------------------

    def execute(self, name: str, arguments: Optional[dict] = None) -> ToolResult:
        tool = self.get(name)

        if tool is None:
            return ToolResult.failure(f"Unbekanntes Tool: {name}")

        decision = self.policy.check(tool)

        if not decision.allowed:
            logger.warning(f"{name} abgelehnt: {decision.reason}")
            return ToolResult.failure(decision.reason)

        logger.info(f"Führe aus: {name} {arguments or {}}")

        try:
            result = tool.execute(arguments)
        except Exception as error:  # doppelte Absicherung
            logger.error(f"{name} unerwartet fehlgeschlagen: {error}")
            return ToolResult.failure(str(error))

        if not result.ok:
            logger.warning(f"{name} ohne Erfolg: {result.error}")

        return result
