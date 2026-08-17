"""
JARVIS Zeit-Tools

Uhrzeit, Datum und Wochentag kommen aus dem System, niemals aus dem LLM.
"""

from datetime import datetime, timezone
from typing import Any, List

from src.tools.base import RiskLevel, Tool, ToolParameter, ToolResult

WEEKDAYS = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)

MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)


def now_local() -> datetime:
    """Aktuelle lokale Zeit inklusive Zeitzoneninformation."""
    return datetime.now(timezone.utc).astimezone()


def format_german(moment: datetime) -> str:
    return (
        f"{WEEKDAYS[moment.weekday()]}, "
        f"{moment.day}. {MONTHS[moment.month - 1]} {moment.year}, "
        f"{moment.strftime('%H:%M')} Uhr"
    )


class CurrentTimeTool(Tool):
    name = "current_time"
    description = "Liefert aktuelle Uhrzeit, Datum, Wochentag und Zeitzone."
    parameters: List[ToolParameter] = []
    risk = RiskLevel.SAFE

    def run(self, **kwargs: Any) -> ToolResult:
        moment = now_local()
        zone = moment.tzname() or "lokal"

        return ToolResult.success(
            f"{format_german(moment)} ({zone})",
            iso=moment.isoformat(timespec="seconds"),
            weekday=WEEKDAYS[moment.weekday()],
            date=moment.strftime("%Y-%m-%d"),
            time=moment.strftime("%H:%M"),
            timezone=zone,
        )
