"""
JARVIS Orchestrator

Der Ablauf einer Anfrage:

    Nachricht
      → IntentAnalyzer   (ein LLM-Aufruf: Memory-Aktion, Bereich, Werkzeug)
      → MemoryManager    (speichern, ändern, löschen)
      → ToolManager      (Werkzeug mit Rechteprüfung ausführen)
      → Antwort          (ein LLM-Aufruf mit Memory- und Werkzeugkontext)

Damit bleibt es bei zwei LLM-Aufrufen pro Anfrage.
"""

from typing import Any, Dict, List, Optional, Sequence

from config.config import config
from config.models import TaskType
from src.core.context import ConversationContext
from src.core.intent import IntentAnalyzer
from src.core.memory_manager import MemoryManager
from src.core.state import AssistantState, SystemState
from src.core.tool_manager import ToolManager
from src.llm.model_manager import ModelManager
from src.llm.prompts import build_system_prompt, build_tool_result_prompt
from src.memory.memory import Memory
from src.memory.models import MemoryEntry, entries_to_text
from src.utils.logging import CORE, get_logger

logger = get_logger(CORE)


class Orchestrator:
    """Koordiniert Analyse, Gedächtnis, Werkzeuge und Antwort."""

    def __init__(
        self,
        memory: Memory,
        model_manager: ModelManager,
        context: ConversationContext,
        state: SystemState,
        tool_manager: Optional[ToolManager] = None,
    ):
        self.memory = memory
        self.model_manager = model_manager
        self.context = context
        self.state = state
        self.memory_manager = MemoryManager(memory)
        self.tool_manager = tool_manager

        self.intent_analyzer = IntentAnalyzer(
            model_manager=model_manager,
            tool_descriptions=tool_manager.descriptions if tool_manager else "",
            known_tools=tool_manager.names if tool_manager else None,
        )

    # ------------------------------------------------------------
    # Einzelschritte
    # ------------------------------------------------------------

    def analyze(self, message: str) -> Dict[str, Any]:
        return self.intent_analyzer.analyze(message)

    def build_memory_text(self, memories: Sequence[Any]) -> str:
        if not memories:
            return "Keine relevanten gespeicherten Informationen."

        entries: List[MemoryEntry] = []

        for item in memories:
            if isinstance(item, MemoryEntry):
                entries.append(item)
            else:
                entries.append(MemoryEntry.from_row(item))

        return entries_to_text(entries)

    def generate_response(
        self,
        memories: Sequence[Any],
        tool_context: str = "",
    ) -> str:
        system_prompt = build_system_prompt(
            self.build_memory_text(memories),
            user_name=config.user_name,
        )

        if tool_context:
            system_prompt = f"{system_prompt}\n{tool_context}"

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        messages.extend(self.context.get_recent_history())

        try:
            answer = self.model_manager.chat(
                messages=messages,
                task_type=TaskType.CHAT,
                json_mode=False,
            )
            return answer.strip()
        except Exception as error:
            logger.error(f"Antwort konnte nicht erzeugt werden: {error}")
            self.state.record_error(str(error))
            return (
                "Entschuldigung, Sir. Mein lokales Sprachmodell "
                "ist momentan nicht erreichbar."
            )

    # ------------------------------------------------------------
    # Gesamtablauf
    # ------------------------------------------------------------

    def respond(self, message: str) -> str:
        message = message.strip()

        if not message:
            return "Wie kann ich Ihnen helfen, Sir?"

        self.context.add_user_message(message)
        self.state.set_mode(AssistantState.THINKING)

        analysis = self.analyze(message)
        logger.info(f"Analyse: {analysis}")

        self.memory_manager.process(analysis)
        self.state.update_memory_count(self.memory.count())
        self.state.active_scope = analysis.get("memory_scope", "KEINE")

        tool_context = ""

        if self.tool_manager is not None:
            result = self.tool_manager.run_from_analysis(analysis)

            if result is not None:
                tool_context = build_tool_result_prompt(
                    analysis["tool"],
                    self.tool_manager.result_text(analysis["tool"], result),
                )

        memories = self.memory_manager.relevant(analysis)

        answer = self.generate_response(memories, tool_context)

        self.context.add_assistant_message(answer)
        self.state.set_mode(AssistantState.IDLE)

        return answer
