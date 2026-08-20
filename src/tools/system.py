"""
JARVIS System-Tools

Informationen über den Rechner: Betriebssystem, Speicherplatz, Auslastung,
sowie Lautstärkesteuerung, soweit das System sie anbietet.

psutil ist optional: fehlt es, liefert JARVIS die Werte, die die
Standardbibliothek hergibt, statt einen Fehler zu werfen.
"""

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from src.tools.base import RiskLevel, Tool, ToolParameter, ToolResult

try:  # optional
    import psutil
except ImportError:  # pragma: no cover - abhängig von der Installation
    psutil = None


def _format_bytes(value: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


class SystemInfoTool(Tool):
    name = "system_info"
    description = "Liefert Betriebssystem, Prozessor, Arbeitsspeicher und Auslastung."
    parameters: List[ToolParameter] = []
    risk = RiskLevel.SAFE

    def run(self, **kwargs: Any) -> ToolResult:
        lines = [
            f"System: {platform.system()} {platform.release()}",
            f"Rechner: {platform.node()}",
            f"Prozessor: {platform.processor() or platform.machine()}",
            f"Python: {platform.python_version()}",
        ]

        data = {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        }

        if psutil is not None:
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.2)
            lines.append(
                f"Arbeitsspeicher: {_format_bytes(memory.used)} von "
                f"{_format_bytes(memory.total)} belegt ({memory.percent} %)"
            )
            lines.append(f"CPU-Auslastung: {cpu} %")
            data.update(
                memory_total=memory.total,
                memory_used=memory.used,
                memory_percent=memory.percent,
                cpu_percent=cpu,
            )

        return ToolResult.success("\n".join(lines), **data)


class DiskSpaceTool(Tool):
    name = "disk_space"
    description = "Zeigt freien und belegten Speicherplatz eines Laufwerks oder Pfads."
    parameters: List[ToolParameter] = [
        ToolParameter(
            name="path",
            description="Pfad oder Laufwerk, Standard: Benutzerverzeichnis",
            required=False,
        )
    ]
    risk = RiskLevel.SAFE

    def run(self, path: Optional[str] = None, **kwargs: Any) -> ToolResult:
        target = Path(path).expanduser() if path else Path.home()

        if not target.exists():
            return ToolResult.failure(f"Pfad existiert nicht: {target}")

        usage = shutil.disk_usage(target)

        return ToolResult.success(
            f"{target}: {_format_bytes(usage.free)} frei von "
            f"{_format_bytes(usage.total)} "
            f"({_format_bytes(usage.used)} belegt)",
            total=usage.total,
            used=usage.used,
            free=usage.free,
            path=str(target),
        )


class VolumeTool(Tool):
    """
    Lautstärke setzen.

    Linux: pactl bzw. amixer.
    Windows/macOS: aktuell nicht unterstützt – das Tool meldet das ehrlich,
    statt still zu scheitern.
    """

    name = "set_volume"
    description = "Setzt die Systemlautstärke in Prozent (0-100)."
    parameters: List[ToolParameter] = [
        ToolParameter(name="percent", description="Lautstärke 0-100", type="number")
    ]
    risk = RiskLevel.SENSITIVE

    def is_available(self) -> bool:
        return platform.system() == "Linux" and (
            shutil.which("pactl") is not None or shutil.which("amixer") is not None
        )

    def run(self, percent: Any, **kwargs: Any) -> ToolResult:
        try:
            level = max(0, min(100, int(float(percent))))
        except (TypeError, ValueError):
            return ToolResult.failure("Lautstärke muss eine Zahl zwischen 0 und 100 sein.")

        if not self.is_available():
            return ToolResult.failure(
                "Lautstärkesteuerung ist auf diesem System noch nicht eingerichtet."
            )

        if shutil.which("pactl"):
            command = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"]
        else:
            command = ["amixer", "-q", "sset", "Master", f"{level}%"]

        result = subprocess.run(command, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return ToolResult.failure(result.stderr.strip() or "Lautstärke nicht änderbar.")

        return ToolResult.success(f"Lautstärke auf {level} % gesetzt.", percent=level)
