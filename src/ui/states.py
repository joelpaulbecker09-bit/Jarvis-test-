"""
Darstellung der JARVIS-Zustände.

Jeder Zustand hat eine eigene Farbe, Pulsstärke und Beschriftung. So ist
auf einen Blick erkennbar, ob JARVIS wartet, zuhört, denkt oder spricht.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

from src.core.state import AssistantState

BACKGROUND = "#05070a"
FOREGROUND = "#e8f4ff"
MUTED = "#5d6b7a"


@dataclass(frozen=True)
class StateStyle:
    """Aussehen eines Zustands."""

    label: str
    color: Tuple[int, int, int]
    glow: Tuple[int, int, int]
    pulse: float
    rotation: float


STYLES: Dict[AssistantState, StateStyle] = {
    AssistantState.IDLE: StateStyle(
        label="Bereit",
        color=(64, 156, 255),
        glow=(20, 70, 130),
        pulse=0.05,
        rotation=0.004,
    ),
    AssistantState.LISTENING: StateStyle(
        label="Ich höre zu",
        color=(80, 220, 255),
        glow=(20, 110, 150),
        pulse=0.16,
        rotation=0.010,
    ),
    AssistantState.THINKING: StateStyle(
        label="Ich denke nach",
        color=(150, 130, 255),
        glow=(60, 50, 150),
        pulse=0.10,
        rotation=0.020,
    ),
    AssistantState.SPEAKING: StateStyle(
        label="Ich spreche",
        color=(110, 200, 255),
        glow=(30, 100, 170),
        pulse=0.22,
        rotation=0.012,
    ),
    AssistantState.ERROR: StateStyle(
        label="Störung",
        color=(255, 96, 96),
        glow=(120, 30, 30),
        pulse=0.08,
        rotation=0.003,
    ),
}


def style_for(state: AssistantState) -> StateStyle:
    return STYLES.get(state, STYLES[AssistantState.IDLE])


def to_hex(color: Tuple[int, int, int]) -> str:
    red, green, blue = (max(0, min(255, int(value))) for value in color)
    return f"#{red:02x}{green:02x}{blue:02x}"


def blend(
    color: Tuple[int, int, int],
    other: Tuple[int, int, int],
    factor: float,
) -> Tuple[int, int, int]:
    """Mischt zwei Farben; factor 0.0 = color, 1.0 = other."""
    factor = max(0.0, min(1.0, factor))

    return tuple(  # type: ignore[return-value]
        int(left + (right - left) * factor) for left, right in zip(color, other)
    )
