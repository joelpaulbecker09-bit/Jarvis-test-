"""
JARVIS Sicherheitsschicht

Kein Tool wird blind ausgeführt. Vor jeder Ausführung entscheidet die
PermissionPolicy anhand der Konfiguration und der Risikostufe:

    erlaubt · Rückfrage nötig · verboten
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from config.config import config
from src.tools.base import RiskLevel, Tool
from src.utils.logging import TOOL, get_logger

logger = get_logger(TOOL)

# Rückfrage beim Benutzer: Frage -> Zustimmung
ConfirmHandler = Callable[[str], bool]


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


class PermissionPolicy:
    """
    Regelt, welche Tools ausgeführt werden dürfen.

    Standardwerte kommen aus config.section("tools"):
        allow_terminal, allow_file_write, allow_file_delete,
        confirm_dangerous, file_roots
    """

    def __init__(
        self,
        confirm_handler: Optional[ConfirmHandler] = None,
        settings: Optional[dict] = None,
    ):
        self.settings = settings if settings is not None else config.section("tools")
        self.confirm_handler = confirm_handler

    # ------------------------------------------------------------
    # Grundregeln
    # ------------------------------------------------------------

    @property
    def allow_terminal(self) -> bool:
        return bool(self.settings.get("allow_terminal", False))

    @property
    def allow_file_write(self) -> bool:
        return bool(self.settings.get("allow_file_write", True))

    @property
    def allow_file_delete(self) -> bool:
        return bool(self.settings.get("allow_file_delete", False))

    @property
    def confirm_dangerous(self) -> bool:
        return bool(self.settings.get("confirm_dangerous", True))

    @property
    def file_roots(self) -> Sequence[Path]:
        roots = self.settings.get("file_roots") or []
        return [Path(root).expanduser().resolve() for root in roots]

    # ------------------------------------------------------------
    # Prüfung
    # ------------------------------------------------------------

    def check(self, tool: Tool) -> PermissionDecision:
        """
        Prüft, ob ein Tool ausgeführt werden darf.
        """
        if tool.name == "terminal_command" and not self.allow_terminal:
            return PermissionDecision(
                allowed=False,
                reason=(
                    "Terminal-Befehle sind deaktiviert. "
                    "Aktivierbar über config/settings.json → tools.allow_terminal."
                ),
            )

        if tool.name in {"write_file", "create_file", "move_file"} and not self.allow_file_write:
            return PermissionDecision(
                allowed=False,
                reason="Schreibzugriff auf Dateien ist deaktiviert (tools.allow_file_write).",
            )

        if tool.name == "delete_file" and not self.allow_file_delete:
            return PermissionDecision(
                allowed=False,
                reason="Löschen von Dateien ist deaktiviert (tools.allow_file_delete).",
            )

        if tool.risk is RiskLevel.SAFE:
            return PermissionDecision(allowed=True)

        if tool.risk is RiskLevel.SENSITIVE:
            return PermissionDecision(allowed=True)

        if not self.confirm_dangerous:
            return PermissionDecision(allowed=True)

        return self.confirm(f"Soll ich {tool.name} wirklich ausführen, Sir?")

    def confirm(self, question: str) -> PermissionDecision:
        """
        Holt die Zustimmung des Benutzers für eine einzelne Aktion ein.
        """
        if not self.confirm_dangerous:
            return PermissionDecision(allowed=True)

        if self.confirm_handler is None:
            return PermissionDecision(
                allowed=False,
                reason=f"{question} (Bestätigung nötig, aber keine Rückfrage möglich)",
            )

        try:
            approved = bool(self.confirm_handler(question))
        except Exception as error:
            logger.error(f"Rückfrage fehlgeschlagen: {error}")
            return PermissionDecision(allowed=False, reason="Rückfrage fehlgeschlagen.")

        if approved:
            return PermissionDecision(allowed=True)

        return PermissionDecision(allowed=False, reason="Vom Benutzer abgelehnt.")

    # ------------------------------------------------------------
    # Dateipfade
    # ------------------------------------------------------------

    def check_path(self, path: Path) -> PermissionDecision:
        """
        Beschränkt Dateizugriffe auf die konfigurierten Wurzelverzeichnisse.
        Ohne konfigurierte Wurzeln ist nur das Benutzerverzeichnis erlaubt.
        """
        resolved = Path(path).expanduser().resolve()
        roots = list(self.file_roots) or [Path.home().resolve()]

        for root in roots:
            if resolved == root or root in resolved.parents:
                return PermissionDecision(allowed=True)

        return PermissionDecision(
            allowed=False,
            reason=(
                f"Zugriff auf {resolved} ist nicht erlaubt. "
                f"Erlaubt sind: {', '.join(str(root) for root in roots)}"
            ),
        )
