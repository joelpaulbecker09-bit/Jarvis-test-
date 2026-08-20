"""
JARVIS Tool Base

Grundlage des Tool-Systems: ein Tool beschreibt sich selbst
(Name, Zweck, Parameter, Risiko) und liefert immer ein ToolResult –
niemals eine Ausnahme nach außen.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.utils.logging import TOOL, get_logger

logger = get_logger(TOOL)


class RiskLevel(Enum):
    """Wie gefährlich ist die Aktion eines Tools?"""

    SAFE = "safe"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class ToolParameter:
    name: str
    description: str
    type: str = "string"
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    """Einheitliches Ergebnis eines Tool-Aufrufs."""

    ok: bool
    output: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    needs_confirmation: bool = False

    @classmethod
    def success(cls, output: str, **data: Any) -> "ToolResult":
        return cls(ok=True, output=output, data=data)

    @classmethod
    def failure(cls, error: str) -> "ToolResult":
        return cls(ok=False, output="", error=error)

    @classmethod
    def confirmation_required(cls, question: str) -> "ToolResult":
        return cls(ok=False, output=question, needs_confirmation=True)

    def as_text(self) -> str:
        if self.ok:
            return self.output
        return f"Fehler: {self.error or self.output or 'unbekannt'}"


class Tool(ABC):
    """
    Basisklasse aller Tools.

    Unterklassen implementieren ausschließlich run(); Validierung und
    Fehlerbehandlung übernimmt execute().
    """

    name: str = ""
    description: str = ""
    parameters: List[ToolParameter] = []
    risk: RiskLevel = RiskLevel.SAFE

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolResult:
        """Führt die eigentliche Aktion aus."""

    def is_available(self) -> bool:
        """Kann das Tool auf diesem System verwendet werden?"""
        return True

    def execute(self, arguments: Optional[Dict[str, Any]] = None) -> ToolResult:
        arguments = dict(arguments or {})

        missing = [
            parameter.name
            for parameter in self.parameters
            if parameter.required and not arguments.get(parameter.name)
        ]

        if missing:
            return ToolResult.failure(
                f"Fehlende Parameter für {self.name}: {', '.join(missing)}"
            )

        for parameter in self.parameters:
            if parameter.name not in arguments and parameter.default is not None:
                arguments[parameter.name] = parameter.default

        allowed = {parameter.name for parameter in self.parameters}
        unexpected = set(arguments) - allowed

        for key in unexpected:
            arguments.pop(key)

        try:
            result = self.run(**arguments)
        except Exception as error:
            logger.error(f"{self.name} fehlgeschlagen: {error}")
            return ToolResult.failure(str(error))

        if not isinstance(result, ToolResult):
            return ToolResult.success(str(result))

        return result

    def describe(self) -> str:
        """Kurzbeschreibung für den Tool-Auswahl-Prompt des LLM."""
        if not self.parameters:
            return f"- {self.name}: {self.description} (keine Parameter)"

        parameters = ", ".join(
            f"{parameter.name}"
            + ("" if parameter.required else "?")
            + f" ({parameter.description})"
            for parameter in self.parameters
        )

        return f"- {self.name}: {self.description} | Parameter: {parameters}"
