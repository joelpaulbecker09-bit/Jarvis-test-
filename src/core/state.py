"""
JARVIS System State

Verwaltet den aktuellen Laufzeit-Zustand des JARVIS-Systems.

Der Laufzeitzustand (idle, listening, thinking, speaking, error) ist zugleich
die Grundlage der Oberfläche: die Partikel-Animation richtet sich danach.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from config.config import config


class AssistantState(Enum):
    """Was tut JARVIS gerade?"""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


StateListener = Callable[[AssistantState], None]


@dataclass
class SystemState:
    """
    Hält den Systemstatus von JARVIS.
    """
    is_online: bool = True
    active_model: str = field(default_factory=lambda: config.default_model)
    memory_count: int = 0
    active_scope: str = "KEINE"
    last_error: Optional[str] = None
    mode: AssistantState = AssistantState.IDLE
    audio_level: float = 0.0
    _listeners: List[StateListener] = field(default_factory=list, repr=False)

    def update_memory_count(self, count: int) -> None:
        self.memory_count = count

    def set_active_model(self, model_name: str) -> None:
        self.active_model = model_name

    def record_error(self, error_message: str) -> None:
        self.last_error = error_message
        self.set_mode(AssistantState.ERROR)

    # ------------------------------------------------------------
    # Laufzeitzustand
    # ------------------------------------------------------------

    def set_mode(self, mode: AssistantState) -> None:
        if mode is self.mode:
            return

        self.mode = mode

        for listener in list(self._listeners):
            try:
                listener(mode)
            except Exception:
                # Eine fehlerhafte Anzeige darf JARVIS nicht stoppen.
                continue

    def set_audio_level(self, level: float) -> None:
        self.audio_level = max(0.0, min(1.0, level))

    def add_listener(self, listener: StateListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: StateListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)
