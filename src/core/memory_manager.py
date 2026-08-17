"""
JARVIS Memory-Manager

Führt die vom Analyzer erkannte Memory-Aktion aus:

    NEU · AENDERN · LOESCHEN · KEINE

Bei mehrdeutigen Treffern wird nicht geraten: Ändern und Löschen brechen ab,
statt die falsche Erinnerung zu verändern.
"""

from typing import Any, Dict, List

from src.memory.memory import Memory
from src.memory.models import MemoryEntry
from src.utils.logging import MEMORY, get_logger

logger = get_logger(MEMORY)


class MemoryManager:
    """Kapselt alle Schreibzugriffe auf das Langzeitgedächtnis."""

    def __init__(self, memory: Memory):
        self.memory = memory

    # ------------------------------------------------------------
    # Aktion ausführen
    # ------------------------------------------------------------

    def process(self, analysis: Dict[str, Any]) -> None:
        action = analysis.get("action", "KEINE")

        if action == "NEU":
            self._create(analysis)
        elif action == "LOESCHEN":
            self.delete(analysis.get("search_target", ""))
        elif action == "AENDERN":
            self.update(analysis)

    def _create(self, analysis: Dict[str, Any]) -> None:
        try:
            saved = self.memory.save(
                category=analysis["category"],
                memory_type=analysis["memory_type"],
                entity_type=analysis["entity_type"],
                information=analysis["information"],
                time_context=analysis["time_context"],
            )
        except Exception as error:
            logger.error(f"Memory konnte nicht gespeichert werden: {error}")
            return

        if saved:
            logger.info(
                f"Gespeichert: {analysis['category']} | {analysis['memory_type']} | "
                f"{analysis['entity_type'] or 'Unbekannt'} | {analysis['information']}"
            )
        else:
            logger.info(f"Bereits vorhanden: {analysis['information']}")

    # ------------------------------------------------------------
    # Löschen
    # ------------------------------------------------------------

    def delete(self, search_target: str) -> bool:
        if not search_target:
            return False

        match = self.memory.resolve(search_target)

        if match.best is None:
            if match.ambiguous:
                logger.warning(
                    f"Mehrere mögliche Treffer. Löschen abgebrochen: {search_target}"
                )
            else:
                logger.info(f"Nicht gefunden: {search_target}")
            return False

        if match.best.id is None:
            return False

        deleted = self.memory.delete(match.best.id)

        if deleted:
            logger.info(f"Gelöscht: {match.best.information}")
        else:
            logger.warning(f"Löschen fehlgeschlagen: {match.best.information}")

        return deleted

    # ------------------------------------------------------------
    # Ändern
    # ------------------------------------------------------------

    def update(self, analysis: Dict[str, Any]) -> bool:
        target = analysis.get("search_target", "")

        if not target:
            return False

        match = self.memory.resolve(target, category=analysis.get("category") or None)

        if match.best is None:
            match = self.memory.resolve(target)

        if match.best is None or match.best.id is None:
            logger.warning(f"Änderung nicht eindeutig oder nicht gefunden: {target}")
            return False

        existing = match.best
        time_context = analysis.get("time_context")

        try:
            updated = self.memory.update(
                memory_id=existing.id,
                category=analysis.get("category") or existing.category,
                memory_type=analysis.get("memory_type") or existing.memory_type,
                entity_type=analysis.get("entity_type") or existing.entity_type,
                information=analysis.get("information") or existing.information,
                time_context=(
                    time_context if time_context is not None else existing.time_context
                ),
            )
        except Exception as error:
            logger.error(f"Memory konnte nicht geändert werden: {error}")
            return False

        if updated:
            logger.info(
                f"Geändert: {existing.information} → "
                f"{analysis.get('information') or existing.information}"
            )
        else:
            logger.warning("Änderung fehlgeschlagen.")

        return updated

    # ------------------------------------------------------------
    # Lesen
    # ------------------------------------------------------------

    def relevant(self, analysis: Dict[str, Any]) -> List[MemoryEntry]:
        scope = analysis.get("memory_scope", "KEINE")

        if scope == "KEINE":
            return []

        if scope == "ALLE":
            return self.memory.entries()

        entries = self.memory.entries_by_category(scope)

        search_target = analysis.get("search_target") or analysis.get("information")

        if not entries and search_target:
            entries = [scored.entry for scored in self.memory.search(search_target)]

        return entries
