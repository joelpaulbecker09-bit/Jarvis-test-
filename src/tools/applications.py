"""
JARVIS Anwendungs-Tools

Programme öffnen, schließen und laufende Prozesse auflisten.
Plattformabhängig, aber mit einheitlicher Schnittstelle.
"""

import platform
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from src.tools.base import RiskLevel, Tool, ToolParameter, ToolResult
from src.utils.logging import TOOL, get_logger

try:  # optional
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

logger = get_logger(TOOL)

# Bekannte Programme je Plattform. Alles andere wird direkt als Befehl versucht.
KNOWN_APPLICATIONS: Dict[str, Dict[str, str]] = {
    "Windows": {
        "discord": "discord",
        "spotify": "spotify",
        "browser": "start",
        "explorer": "explorer",
        "editor": "notepad",
        "rechner": "calc",
        "terminal": "wt",
    },
    "Linux": {
        "discord": "discord",
        "spotify": "spotify",
        "browser": "xdg-open https://duckduckgo.com",
        "explorer": "xdg-open .",
        "editor": "gedit",
        "rechner": "gnome-calculator",
        "terminal": "x-terminal-emulator",
    },
    "Darwin": {
        "discord": "Discord",
        "spotify": "Spotify",
        "browser": "Safari",
        "editor": "TextEdit",
        "rechner": "Calculator",
        "terminal": "Terminal",
    },
}


def _resolve_application(name: str) -> str:
    mapping = KNOWN_APPLICATIONS.get(platform.system(), {})
    return mapping.get(name.strip().lower(), name.strip())


class OpenApplicationTool(Tool):
    name = "open_application"
    description = "Startet ein Programm, z. B. 'Discord' oder 'Spotify'."
    parameters = [ToolParameter(name="application", description="Programmname")]
    risk = RiskLevel.SENSITIVE

    def run(self, application: str, **kwargs: Any) -> ToolResult:
        target = _resolve_application(application)
        system = platform.system()

        try:
            if system == "Windows":
                subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", target])
            else:
                executable = target.split()[0]
                if shutil.which(executable) is None:
                    return ToolResult.failure(f"Programm nicht gefunden: {executable}")
                subprocess.Popen(target.split())
        except Exception as error:
            return ToolResult.failure(f"Konnte {application} nicht starten: {error}")

        return ToolResult.success(f"{application} wurde gestartet.", application=target)


class CloseApplicationTool(Tool):
    name = "close_application"
    description = "Beendet ein laufendes Programm."
    parameters = [ToolParameter(name="application", description="Programmname")]
    risk = RiskLevel.DANGEROUS

    def is_available(self) -> bool:
        return psutil is not None or platform.system() == "Windows"

    def run(self, application: str, **kwargs: Any) -> ToolResult:
        target = _resolve_application(application).split()[0].lower()

        if psutil is None:
            if platform.system() != "Windows":
                return ToolResult.failure(
                    "Zum Beenden von Programmen wird psutil benötigt (pip install psutil)."
                )
            result = subprocess.run(
                ["taskkill", "/IM", f"{target}.exe", "/F"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return ToolResult.failure(result.stderr.strip() or "Prozess nicht gefunden.")
            return ToolResult.success(f"{application} wurde beendet.")

        closed = 0

        for process in psutil.process_iter(["name"]):
            process_name = (process.info.get("name") or "").lower()
            if target in process_name.removesuffix(".exe"):
                try:
                    process.terminate()
                    closed += 1
                except Exception as error:
                    logger.warning(f"Prozess {process_name} nicht beendbar: {error}")

        if closed == 0:
            return ToolResult.failure(f"Kein laufender Prozess gefunden: {application}")

        return ToolResult.success(
            f"{application} wurde beendet ({closed} Prozess(e)).", closed=closed
        )


class RunningApplicationsTool(Tool):
    name = "running_applications"
    description = "Listet die aktuell laufenden Programme mit hoher Auslastung."
    parameters: List[ToolParameter] = []
    risk = RiskLevel.SAFE

    def is_available(self) -> bool:
        return psutil is not None

    def run(self, **kwargs: Any) -> ToolResult:
        if psutil is None:
            return ToolResult.failure("psutil ist nicht installiert.")

        processes: List[str] = []
        seen: set = set()

        for process in psutil.process_iter(["name", "memory_percent"]):
            name: Optional[str] = process.info.get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            processes.append(f"{name} ({process.info.get('memory_percent', 0):.1f} % RAM)")

        processes.sort()

        return ToolResult.success("\n".join(processes[:40]), count=len(processes))
