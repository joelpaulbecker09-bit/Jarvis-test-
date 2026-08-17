"""
JARVIS Brain

Das Brain ist die öffentliche Schnittstelle des Systems und bleibt
abwärtskompatibel (respond, analyze_message, process_memory, ...).

Die eigentliche Arbeit ist aufgeteilt:

    IntentAnalyzer  – Analyse der Nachricht
    MemoryManager   – Langzeitgedächtnis
    ToolManager     – Werkzeuge inklusive Rechteprüfung
    Orchestrator    – Ablaufsteuerung
"""

from typing import Any, Callable, Dict, List, Optional, Sequence

from config.config import config
from src.core.context import ConversationContext
from src.core.intent import sanitize_analysis
from src.core.orchestrator import Orchestrator
from src.core.state import SystemState
from src.core.tool_manager import ToolManager
from src.llm.model_manager import ModelManager
from src.memory import models
from src.memory.memory import Memory
from src.tools.registry import ToolRegistry
from src.utils.logging import CORE, get_logger

logger = get_logger(CORE)


class JarvisBrain:
    """
    Verantwortlichkeiten:
    - Benutzeranfragen analysieren
    - Langfristige Informationen erkennen und verwalten
    - Werkzeuge einsetzen
    - Gesprächskontext verwalten
    - Antwort mit lokalem LLM erzeugen
    """

    CATEGORIES = set(models.CATEGORIES)
    MEMORY_TYPES = set(models.MEMORY_TYPES)
    ENTITY_TYPES = set(models.ENTITY_TYPES)
    MEMORY_ACTIONS = set(models.MEMORY_ACTIONS)
    MEMORY_SCOPES = set(models.MEMORY_SCOPES)

    # ============================================================
    # INITIALISIERUNG
    # ============================================================

    def __init__(
        self,
        model_manager: Optional[ModelManager] = None,
        tools_enabled: Optional[bool] = None,
        confirm_handler: Optional[Callable[[str], bool]] = None,
    ):
        self.memory = Memory(database_path=config.memory_db_path)
        self.model_manager = model_manager or ModelManager()
        self.context = ConversationContext(max_history=config.max_history_messages)
        self.state = SystemState(
            active_model=config.default_model,
            memory_count=self.memory.count(),
        )

        if tools_enabled is None:
            tools_enabled = bool(config.section("tools").get("enabled", True))

        self.tool_manager: Optional[ToolManager] = None

        if tools_enabled:
            registry = ToolRegistry(confirm_handler=confirm_handler)
            self.tool_manager = ToolManager(registry)

        self.orchestrator = Orchestrator(
            memory=self.memory,
            model_manager=self.model_manager,
            context=self.context,
            state=self.state,
            tool_manager=self.tool_manager,
        )

        # Abwärtskompatibilität
        self.MODEL = config.default_model

        logger.info("Brain initialisiert.")
        logger.info(f"Modell: {self.MODEL}")
        logger.info(f"Memories: {self.memory.count()}")

    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        return self.context.get_all_history()

    @conversation_history.setter
    def conversation_history(self, history: List[Dict[str, str]]):
        self.context.clear()
        for item in history:
            if item.get("role") == "user":
                self.context.add_user_message(item.get("content", ""))
            elif item.get("role") == "assistant":
                self.context.add_assistant_message(item.get("content", ""))

    # ============================================================
    # LLM ABSTRAKTION (ABWÄRTSKOMPATIBEL)
    # ============================================================

    def _chat(self, messages: List[Dict[str, str]], json_mode: bool = False) -> str:
        return self.model_manager.chat(
            messages=messages,
            model=self.MODEL,
            json_mode=json_mode,
        )

    # ============================================================
    # ANALYSE
    # ============================================================

    def analyze_message(self, message: str) -> Dict[str, Any]:
        return self.orchestrator.analyze(message)

    def _sanitize_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        known_tools = self.tool_manager.names if self.tool_manager else None
        return sanitize_analysis(analysis, known_tools)

    # ============================================================
    # MEMORY
    # ============================================================

    def process_memory(self, analysis: Dict[str, Any]) -> None:
        self.orchestrator.memory_manager.process(analysis)
        self.state.update_memory_count(self.memory.count())

    def get_relevant_memories(self, analysis: Dict[str, Any]) -> List[Any]:
        return self.orchestrator.memory_manager.relevant(analysis)

    def build_memory_text(self, memories: Sequence[Any]) -> str:
        return self.orchestrator.build_memory_text(memories)

    # ============================================================
    # ANTWORT
    # ============================================================

    def generate_response(
        self,
        message: str,
        analysis: Dict[str, Any],
        memories: Sequence[Any],
    ) -> str:
        return self.orchestrator.generate_response(memories)

    def respond(self, message: str) -> str:
        return self.orchestrator.respond(message)

    # ============================================================
    # WERKZEUGE
    # ============================================================

    def available_tools(self) -> List[str]:
        return self.tool_manager.names if self.tool_manager else []

    def run_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None):
        if self.tool_manager is None:
            raise RuntimeError("Das Tool-System ist deaktiviert.")

        return self.tool_manager.registry.execute(name, arguments)

    # ============================================================
    # MEMORY AUSLESEN
    # ============================================================

    def get_all_memories(self):
        return self.memory.get_all()

    def memory_count(self) -> int:
        return self.memory.count()

    # ============================================================
    # BEENDEN
    # ============================================================

    def close(self) -> None:
        self.memory.close()
