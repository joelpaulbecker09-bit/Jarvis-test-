"""
JARVIS Datei-Tools

Alle Dateizugriffe laufen über die PermissionPolicy: erlaubt sind nur Pfade
innerhalb der konfigurierten Wurzelverzeichnisse (Standard: Benutzerordner).
Löschen und Überschreiben sind zusätzlich abgesichert.
"""

import shutil
from pathlib import Path
from typing import Any, List, Optional

from src.tools.base import RiskLevel, Tool, ToolParameter, ToolResult
from src.tools.permissions import PermissionPolicy

MAX_READ_CHARACTERS = 20000
MAX_SEARCH_RESULTS = 50


class _FileTool(Tool):
    """Gemeinsame Basis: Pfadauflösung und Freigabeprüfung."""

    def __init__(self, policy: Optional[PermissionPolicy] = None):
        self.policy = policy or PermissionPolicy()

    def _resolve(self, path: str) -> Path:
        return Path(path).expanduser().resolve()

    def _check(self, path: Path) -> Optional[ToolResult]:
        decision = self.policy.check_path(path)

        if not decision.allowed:
            return ToolResult.failure(decision.reason)

        return None


class ListDirectoryTool(_FileTool):
    name = "list_directory"
    description = "Listet den Inhalt eines Ordners auf."
    parameters = [ToolParameter(name="path", description="Ordnerpfad")]
    risk = RiskLevel.SAFE

    def run(self, path: str, **kwargs: Any) -> ToolResult:
        target = self._resolve(path)
        denied = self._check(target)
        if denied:
            return denied

        if not target.is_dir():
            return ToolResult.failure(f"Kein Ordner: {target}")

        entries = sorted(
            target.iterdir(),
            key=lambda item: (item.is_file(), item.name.lower()),
        )[:MAX_SEARCH_RESULTS]

        lines = [
            f"{'[Ordner]' if entry.is_dir() else '[Datei] '} {entry.name}"
            for entry in entries
        ]

        return ToolResult.success(
            "\n".join(lines) or "Ordner ist leer.",
            path=str(target),
            count=len(lines),
        )


class FindFileTool(_FileTool):
    name = "find_file"
    description = "Sucht Dateien nach Namensmuster in einem Ordner (rekursiv)."
    parameters = [
        ToolParameter(name="pattern", description="Namensmuster, z. B. '*.pdf'"),
        ToolParameter(
            name="path",
            description="Startordner, Standard: Benutzerverzeichnis",
            required=False,
        ),
    ]
    risk = RiskLevel.SAFE

    def run(self, pattern: str, path: Optional[str] = None, **kwargs: Any) -> ToolResult:
        root = self._resolve(path) if path else Path.home().resolve()
        denied = self._check(root)
        if denied:
            return denied

        if not root.is_dir():
            return ToolResult.failure(f"Kein Ordner: {root}")

        if "*" not in pattern and "?" not in pattern:
            pattern = f"*{pattern}*"

        matches: List[Path] = []

        for candidate in root.rglob(pattern):
            matches.append(candidate)
            if len(matches) >= MAX_SEARCH_RESULTS:
                break

        if not matches:
            return ToolResult.success(f"Keine Treffer für {pattern} in {root}.", count=0)

        return ToolResult.success(
            "\n".join(str(match) for match in matches),
            count=len(matches),
            matches=[str(match) for match in matches],
        )


class ReadFileTool(_FileTool):
    name = "read_file"
    description = "Liest den Textinhalt einer Datei."
    parameters = [ToolParameter(name="path", description="Dateipfad")]
    risk = RiskLevel.SAFE

    def run(self, path: str, **kwargs: Any) -> ToolResult:
        target = self._resolve(path)
        denied = self._check(target)
        if denied:
            return denied

        if not target.is_file():
            return ToolResult.failure(f"Datei nicht gefunden: {target}")

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            return ToolResult.failure(f"Datei nicht lesbar: {error}")

        truncated = len(content) > MAX_READ_CHARACTERS

        return ToolResult.success(
            content[:MAX_READ_CHARACTERS],
            path=str(target),
            truncated=truncated,
        )


class WriteFileTool(_FileTool):
    name = "write_file"
    description = "Schreibt Text in eine Datei (überschreibt oder hängt an)."
    parameters = [
        ToolParameter(name="path", description="Dateipfad"),
        ToolParameter(name="content", description="Inhalt"),
        ToolParameter(
            name="append",
            description="true = anhängen statt überschreiben",
            type="boolean",
            required=False,
        ),
    ]
    risk = RiskLevel.SENSITIVE

    def run(
        self,
        path: str,
        content: str,
        append: Any = False,
        **kwargs: Any,
    ) -> ToolResult:
        target = self._resolve(path)
        denied = self._check(target)
        if denied:
            return denied

        append_mode = str(append).lower() in {"true", "1", "ja", "yes"}

        if target.exists() and not append_mode:
            # Überschreiben vernichtet vorhandenen Inhalt – immer nachfragen.
            decision = self.policy.confirm(
                f"{target} existiert bereits. Soll ich die Datei überschreiben, Sir?"
            )
            if not decision.allowed:
                return ToolResult.failure(decision.reason)

        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "a" if append_mode else "w", encoding="utf-8") as handle:
            handle.write(content)

        return ToolResult.success(
            f"{'Ergänzt' if append_mode else 'Geschrieben'}: {target}",
            path=str(target),
        )


class MoveFileTool(_FileTool):
    name = "move_file"
    description = "Verschiebt oder benennt eine Datei um."
    parameters = [
        ToolParameter(name="source", description="Quellpfad"),
        ToolParameter(name="destination", description="Zielpfad"),
    ]
    risk = RiskLevel.SENSITIVE

    def run(self, source: str, destination: str, **kwargs: Any) -> ToolResult:
        source_path = self._resolve(source)
        destination_path = self._resolve(destination)

        for candidate in (source_path, destination_path):
            denied = self._check(candidate)
            if denied:
                return denied

        if not source_path.exists():
            return ToolResult.failure(f"Quelle nicht gefunden: {source_path}")

        if destination_path.exists():
            return ToolResult.failure(f"Ziel existiert bereits: {destination_path}")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))

        return ToolResult.success(f"Verschoben: {source_path} → {destination_path}")


class CopyFileTool(_FileTool):
    name = "copy_file"
    description = "Kopiert eine Datei."
    parameters = [
        ToolParameter(name="source", description="Quellpfad"),
        ToolParameter(name="destination", description="Zielpfad"),
    ]
    risk = RiskLevel.SENSITIVE

    def run(self, source: str, destination: str, **kwargs: Any) -> ToolResult:
        source_path = self._resolve(source)
        destination_path = self._resolve(destination)

        for candidate in (source_path, destination_path):
            denied = self._check(candidate)
            if denied:
                return denied

        if not source_path.is_file():
            return ToolResult.failure(f"Quelldatei nicht gefunden: {source_path}")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)

        return ToolResult.success(f"Kopiert: {source_path} → {destination_path}")


class DeleteFileTool(_FileTool):
    name = "delete_file"
    description = "Löscht eine Datei. Erfordert Freigabe und Bestätigung."
    parameters = [ToolParameter(name="path", description="Dateipfad")]
    risk = RiskLevel.DANGEROUS

    def run(self, path: str, **kwargs: Any) -> ToolResult:
        target = self._resolve(path)
        denied = self._check(target)
        if denied:
            return denied

        if not target.exists():
            return ToolResult.failure(f"Datei nicht gefunden: {target}")

        if target.is_dir():
            return ToolResult.failure(
                "Ordner werden aus Sicherheitsgründen nicht gelöscht."
            )

        target.unlink()

        return ToolResult.success(f"Gelöscht: {target}")
