"""
JARVIS Erinnerungen und Aufgaben

Persistenz in einer eigenen SQLite-Datei (data/reminders.db), damit das
bestehende Memory unangetastet bleibt.

Unterstützte Zeitangaben (deutsch):
    "in 10 minuten", "in 2 stunden", "morgen um 8", "heute um 18:30",
    "am 24.12. um 10:00", "2026-01-05 09:00"
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional

from config.config import config
from src.tools.base import RiskLevel, Tool, ToolParameter, ToolResult
from src.utils.logging import TOOL, get_logger

logger = get_logger(TOOL)

WEEKDAYS = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]


@dataclass(frozen=True)
class Reminder:
    id: int
    text: str
    due_at: Optional[datetime]
    done: bool

    def as_text(self) -> str:
        if self.due_at is None:
            return f"[{self.id}] {self.text}"
        moment = self.due_at
        return (
            f"[{self.id}] {self.text} – "
            f"{WEEKDAYS[moment.weekday()]}, {moment.strftime('%d.%m.%Y um %H:%M')}"
        )


def parse_german_time(value: str, reference: Optional[datetime] = None) -> Optional[datetime]:
    """
    Wandelt eine deutsche Zeitangabe in einen Zeitpunkt um.
    Gibt None zurück, wenn nichts erkannt wurde (Aufgabe ohne Termin).
    """
    if not value:
        return None

    now = reference or datetime.now()
    text = value.strip().lower()

    relative = re.search(r"in\s+(\d+)\s*(minute|minuten|stunde|stunden|tag|tagen)", text)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        if unit.startswith("minute"):
            return now + timedelta(minutes=amount)
        if unit.startswith("stunde"):
            return now + timedelta(hours=amount)
        return now + timedelta(days=amount)

    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})[ t]?(\d{1,2})?:?(\d{2})?", text)
    if iso:
        return datetime(
            int(iso.group(1)),
            int(iso.group(2)),
            int(iso.group(3)),
            int(iso.group(4) or 9),
            int(iso.group(5) or 0),
        )

    clock = re.search(r"(\d{1,2})(?::(\d{2}))?\s*uhr|um\s+(\d{1,2})(?::(\d{2}))?", text)
    hour: Optional[int] = None
    minute = 0

    if clock:
        hour = int(clock.group(1) or clock.group(3))
        minute = int(clock.group(2) or clock.group(4) or 0)

    date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.?(\d{4})?", text)
    if date_match:
        year = int(date_match.group(3) or now.year)
        candidate = datetime(
            year,
            int(date_match.group(2)),
            int(date_match.group(1)),
            hour if hour is not None else 9,
            minute,
        )
        if candidate < now and date_match.group(3) is None:
            candidate = candidate.replace(year=year + 1)
        return candidate

    day_offset = 0
    if "übermorgen" in text:
        day_offset = 2
    elif "morgen" in text:
        day_offset = 1

    if hour is None and day_offset == 0:
        return None

    base = (now + timedelta(days=day_offset)).replace(
        hour=hour if hour is not None else 9,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if base <= now and day_offset == 0:
        base += timedelta(days=1)

    return base


class ReminderStore:
    """Kleine SQLite-Ablage für Erinnerungen und Aufgaben."""

    def __init__(self, database: Optional[Path] = None):
        self.database = database or (Path(config.data_dir) / "reminders.db")
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    due_at TEXT,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        logger.info(f"Erinnerungen: {self.database}")

    def add(self, text: str, due_at: Optional[datetime]) -> Reminder:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO reminders (text, due_at) VALUES (?, ?)",
                (text, due_at.isoformat(timespec="minutes") if due_at else None),
            )
            reminder_id = int(cursor.lastrowid)

        return Reminder(id=reminder_id, text=text, due_at=due_at, done=False)

    def list(self, include_done: bool = False) -> List[Reminder]:
        query = "SELECT id, text, due_at, done FROM reminders"
        if not include_done:
            query += " WHERE done = 0"
        query += " ORDER BY due_at IS NULL, due_at ASC, id ASC"

        with self._connect() as connection:
            rows = connection.execute(query).fetchall()

        return [
            Reminder(
                id=row[0],
                text=row[1],
                due_at=datetime.fromisoformat(row[2]) if row[2] else None,
                done=bool(row[3]),
            )
            for row in rows
        ]

    def due(self, moment: Optional[datetime] = None) -> List[Reminder]:
        now = moment or datetime.now()
        return [
            reminder
            for reminder in self.list()
            if reminder.due_at is not None and reminder.due_at <= now
        ]

    def complete(self, reminder_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE reminders SET done = 1 WHERE id = ? AND done = 0",
                (reminder_id,),
            )
            return cursor.rowcount > 0

    def delete(self, reminder_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM reminders WHERE id = ?", (reminder_id,)
            )
            return cursor.rowcount > 0


class AddReminderTool(Tool):
    name = "add_reminder"
    description = "Legt eine Erinnerung oder Aufgabe an, z. B. 'in 10 Minuten Ofen prüfen'."
    parameters = [
        ToolParameter(name="text", description="Was soll erinnert werden?"),
        ToolParameter(
            name="when",
            description="Zeitangabe, z. B. 'morgen um 8'",
            required=False,
        ),
    ]
    risk = RiskLevel.SAFE

    def __init__(self, store: Optional[ReminderStore] = None):
        self.store = store or ReminderStore()

    def run(self, text: str, when: Optional[str] = None, **kwargs: Any) -> ToolResult:
        due_at = parse_german_time(when or text)
        reminder = self.store.add(text.strip(), due_at)

        if due_at is None:
            return ToolResult.success(
                f"Aufgabe notiert: {reminder.text}", reminder_id=reminder.id
            )

        return ToolResult.success(
            f"Erinnerung gesetzt: {reminder.as_text()}",
            reminder_id=reminder.id,
            due_at=due_at.isoformat(timespec="minutes"),
        )


class ListRemindersTool(Tool):
    name = "list_reminders"
    description = "Zeigt offene Erinnerungen und Aufgaben."
    parameters: List[ToolParameter] = []
    risk = RiskLevel.SAFE

    def __init__(self, store: Optional[ReminderStore] = None):
        self.store = store or ReminderStore()

    def run(self, **kwargs: Any) -> ToolResult:
        reminders = self.store.list()

        if not reminders:
            return ToolResult.success("Es stehen keine Erinnerungen an.", count=0)

        return ToolResult.success(
            "\n".join(reminder.as_text() for reminder in reminders),
            count=len(reminders),
        )


class CompleteReminderTool(Tool):
    name = "complete_reminder"
    description = "Markiert eine Erinnerung anhand ihrer Nummer als erledigt."
    parameters = [ToolParameter(name="reminder_id", description="Nummer", type="number")]
    risk = RiskLevel.SAFE

    def __init__(self, store: Optional[ReminderStore] = None):
        self.store = store or ReminderStore()

    def run(self, reminder_id: Any, **kwargs: Any) -> ToolResult:
        try:
            identifier = int(reminder_id)
        except (TypeError, ValueError):
            return ToolResult.failure("Die Nummer der Erinnerung muss eine Zahl sein.")

        if not self.store.complete(identifier):
            return ToolResult.failure(f"Keine offene Erinnerung mit Nummer {identifier}.")

        return ToolResult.success(f"Erinnerung {identifier} ist erledigt.")


class DeleteReminderTool(Tool):
    name = "delete_reminder"
    description = "Löscht eine Erinnerung anhand ihrer Nummer."
    parameters = [ToolParameter(name="reminder_id", description="Nummer", type="number")]
    risk = RiskLevel.SENSITIVE

    def __init__(self, store: Optional[ReminderStore] = None):
        self.store = store or ReminderStore()

    def run(self, reminder_id: Any, **kwargs: Any) -> ToolResult:
        try:
            identifier = int(reminder_id)
        except (TypeError, ValueError):
            return ToolResult.failure("Die Nummer der Erinnerung muss eine Zahl sein.")

        if not self.store.delete(identifier):
            return ToolResult.failure(f"Keine Erinnerung mit Nummer {identifier}.")

        return ToolResult.success(f"Erinnerung {identifier} gelöscht.")
