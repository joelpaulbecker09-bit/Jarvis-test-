"""
JARVIS Terminal-Tool

Führt Systembefehle aus – aber niemals blind:

    Brain → Tool → PermissionPolicy → Ausführung

Es gibt keine Shell-Interpolation (kein shell=True), eine Blockliste
offensichtlich zerstörerischer Befehle und ein hartes Zeitlimit.
"""

import platform
import shlex
import subprocess
from typing import Any, List, Optional

from config.config import config
from src.tools.base import RiskLevel, Tool, ToolParameter, ToolResult
from src.tools.permissions import PermissionPolicy

# Befehle, die JARVIS grundsätzlich nicht ausführt.
BLOCKED_COMMANDS = {
    "rm", "rmdir", "del", "erase", "format", "mkfs", "diskpart",
    "shutdown", "reboot", "halt", "poweroff",
    "dd", "chmod", "chown", "icacls", "takeown",
    "reg", "regedit", "bcdedit", "sfc",
    "sudo", "su", "runas", "doas",
}

BLOCKED_FRAGMENTS = ("&&", "||", "|", ">", "<", ";", "`", "$(")

MAX_OUTPUT_CHARACTERS = 4000


class TerminalTool(Tool):
    name = "terminal_command"
    description = (
        "Führt einen einzelnen Systembefehl aus (nur lesende/harmlose Befehle, "
        "keine Pipes oder Umleitungen)."
    )
    parameters = [
        ToolParameter(name="command", description="Auszuführender Befehl"),
        ToolParameter(
            name="working_directory",
            description="Arbeitsverzeichnis",
            required=False,
        ),
    ]
    risk = RiskLevel.DANGEROUS

    def __init__(self, policy: Optional[PermissionPolicy] = None):
        self.policy = policy or PermissionPolicy()
        self.timeout = int(config.section("tools").get("terminal_timeout", 20))

    def run(
        self,
        command: str,
        working_directory: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        cleaned = command.strip()

        if not cleaned:
            return ToolResult.failure("Kein Befehl angegeben.")

        for fragment in BLOCKED_FRAGMENTS:
            if fragment in cleaned:
                return ToolResult.failure(
                    f"Verkettete Befehle sind nicht erlaubt ('{fragment}')."
                )

        try:
            parts: List[str] = shlex.split(cleaned, posix=platform.system() != "Windows")
        except ValueError as error:
            return ToolResult.failure(f"Befehl nicht lesbar: {error}")

        if not parts:
            return ToolResult.failure("Kein Befehl angegeben.")

        executable = parts[0].lower().removesuffix(".exe")

        if executable in BLOCKED_COMMANDS:
            return ToolResult.failure(
                f"'{executable}' steht auf der Sperrliste und wird nicht ausgeführt."
            )

        try:
            completed = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=working_directory or None,
                shell=False,
            )
        except FileNotFoundError:
            return ToolResult.failure(f"Befehl nicht gefunden: {parts[0]}")
        except subprocess.TimeoutExpired:
            return ToolResult.failure(f"Zeitlimit von {self.timeout} Sekunden überschritten.")

        output = (completed.stdout or "").strip()
        error_output = (completed.stderr or "").strip()

        if completed.returncode != 0:
            return ToolResult.failure(
                (error_output or output or "Befehl fehlgeschlagen.")[:MAX_OUTPUT_CHARACTERS]
            )

        return ToolResult.success(
            (output or "Befehl ausgeführt.")[:MAX_OUTPUT_CHARACTERS],
            returncode=completed.returncode,
        )
