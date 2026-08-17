"""
JARVIS Memory Models

Typisierte Repräsentation eines Memory-Eintrags.
Die SQLite-Schicht liefert Tupel; diese Modelle machen sie lesbar,
ohne die bestehende Tupel-API zu entfernen.
"""

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence, Tuple

# Erlaubte Werte – eine einzige Quelle der Wahrheit für Memory und Brain.

CATEGORIES = (
    "Persönlichkeit",
    "Musik",
    "Spiele",
    "Arbeit",
    "Schule",
    "Familie",
    "Freunde",
    "Hobbys",
    "Vorlieben",
    "Abneigungen",
    "Ziele",
    "Gewohnheiten",
    "Sonstiges",
)

MEMORY_TYPES = (
    "Vorliebe",
    "Abneigung",
    "Fakt",
    "Ziel",
    "Gewohnheit",
)

ENTITY_TYPES = (
    "Person",
    "Künstler",
    "Band",
    "Song",
    "Album",
    "Spiel",
    "Film",
    "Serie",
    "Hobby",
    "Tätigkeit",
    "Ort",
    "Gegenstand",
    "Tier",
    "Sonstiges",
)

MEMORY_ACTIONS = (
    "NEU",
    "AENDERN",
    "LOESCHEN",
    "KEINE",
)

MEMORY_SCOPES = CATEGORIES + ("ALLE", "KEINE")


@dataclass(frozen=True)
class MemoryEntry:
    """Ein einzelner Langzeit-Eintrag."""

    id: Optional[int]
    category: str
    memory_type: str
    entity_type: Optional[str]
    information: str
    time_context: Optional[str] = None

    @classmethod
    def from_row_with_id(cls, row: Sequence[Any]) -> "MemoryEntry":
        """Erzeugt einen Eintrag aus (id, category, memory_type, entity_type, information, time_context, ...)."""
        return cls(
            id=row[0],
            category=row[1],
            memory_type=row[2],
            entity_type=row[3],
            information=row[4],
            time_context=row[5] if len(row) > 5 else None,
        )

    @classmethod
    def from_row(cls, row: Sequence[Any]) -> "MemoryEntry":
        """Erzeugt einen Eintrag aus (category, memory_type, entity_type, information, time_context)."""
        return cls(
            id=None,
            category=row[0],
            memory_type=row[1],
            entity_type=row[2],
            information=row[3],
            time_context=row[4] if len(row) > 4 else None,
        )

    def as_row(self) -> Tuple[str, str, Optional[str], str, Optional[str]]:
        return (
            self.category,
            self.memory_type,
            self.entity_type,
            self.information,
            self.time_context,
        )

    def as_text(self) -> str:
        line = (
            f"- Kategorie: {self.category} | "
            f"Typ: {self.memory_type} | "
            f"Objekttyp: {self.entity_type or 'Unbekannt'} | "
            f"Information: {self.information}"
        )

        if self.time_context:
            line += f" | Zeit: {self.time_context}"

        return line


def entries_to_text(entries: Iterable[MemoryEntry]) -> str:
    """Formatiert Einträge für den System-Prompt."""
    lines = [entry.as_text() for entry in entries]

    if not lines:
        return "Keine relevanten gespeicherten Informationen."

    return "\n".join(lines)
