"""
JARVIS System State

Verwaltet den aktuellen Laufzeit-Zustand des JARVIS-Systems.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from config.config import config


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

    def update_memory_count(self, count: int) -> None:
        self.memory_count = count

    def set_active_model(self, model_name: str) -> None:
        self.active_model = model_name

    def record_error(self, error_message: str) -> None:
        self.last_error = error_message
