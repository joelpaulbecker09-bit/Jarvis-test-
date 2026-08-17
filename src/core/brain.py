import json
from typing import Any, Dict, List, Optional

from config.config import config
from config.models import TaskType
from src.core.context import ConversationContext
from src.core.state import SystemState
from src.llm.model_manager import ModelManager
from src.llm.prompts import ANALYZER_SYSTEM_PROMPT, build_system_prompt
from src.memory.memory import Memory


class JarvisBrain:
    """
    JARVIS V6 Brain (Refactored Core Architecture)

    Verantwortlichkeiten:
    - Benutzeranfragen analysieren
    - Langfristige Informationen erkennen
    - Memory automatisch verwalten
    - Memory gezielt laden
    - Gesprächskontext verwalten (via ConversationContext)
    - LLM-Kommunikation steuern (via ModelManager)
    - Finale Antwort mit lokalem LLM erzeugen

    Memory:
        SQLite über src.memory.memory.Memory
    """

    # ============================================================
    # ERLAUBTE WERTE
    # ============================================================

    CATEGORIES = {
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
    }

    MEMORY_TYPES = {
        "Vorliebe",
        "Abneigung",
        "Fakt",
        "Ziel",
        "Gewohnheit",
    }

    ENTITY_TYPES = {
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
    }

    MEMORY_ACTIONS = {
        "NEU",
        "AENDERN",
        "LOESCHEN",
        "KEINE",
    }

    MEMORY_SCOPES = {
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
        "Persönlichkeit",
        "Sonstiges",
        "ALLE",
        "KEINE",
    }

    # ============================================================
    # INITIALISIERUNG
    # ============================================================

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.memory = Memory(database_path=config.memory_db_path)
        self.model_manager = model_manager or ModelManager()
        self.context = ConversationContext(max_history=config.max_history_messages)
        self.state = SystemState(
            active_model=config.default_model,
            memory_count=self.memory.count()
        )

        # Abwärtskompatibilität: Property access auf conversation_history & MODEL
        self.MODEL = config.default_model

        print(f"[JARVIS] Brain initialisiert.")
        print(f"[JARVIS] Modell: {self.MODEL}")
        print(f"[JARVIS] Memories: {self.memory.count()}")

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

    def _chat(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False
    ) -> str:
        """
        Zentraler Aufruf über den ModelManager.
        """
        return self.model_manager.chat(
            messages=messages,
            model=self.MODEL,
            json_mode=json_mode
        )

    # ============================================================
    # ANALYZER
    # ============================================================

    def analyze_message(
        self,
        message: str
    ) -> Dict[str, Any]:
        """
        Analysiert eine Benutzernachricht.
        """
        system_prompt = ANALYZER_SYSTEM_PROMPT

        try:
            content = self.model_manager.chat(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": message,
                    },
                ],
                task_type=TaskType.ANALYSIS,
                json_mode=True,
            )

            analysis = json.loads(content)
            return self._sanitize_analysis(analysis)

        except Exception as error:
            print(f"[ERROR] Analyse fehlgeschlagen: {error}")
            self.state.record_error(str(error))
            return self._empty_analysis()

    # ============================================================
    # ANALYSE BEREINIGEN
    # ============================================================

    def _sanitize_analysis(
        self,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:

        action = str(
            analysis.get("action", "KEINE")
        ).upper().strip()

        if action not in self.MEMORY_ACTIONS:
            action = "KEINE"

        category = str(
            analysis.get("category", "")
        ).strip()

        if category not in self.CATEGORIES:
            category = ""

        memory_type = str(
            analysis.get("memory_type", "")
        ).strip()

        if memory_type not in self.MEMORY_TYPES:
            memory_type = ""

        entity_type = str(
            analysis.get("entity_type", "")
        ).strip()

        if entity_type not in self.ENTITY_TYPES:
            entity_type = ""

        information = str(
            analysis.get("information", "")
        ).strip()

        search_target = str(
            analysis.get("search_target", "")
        ).strip()

        time_context = analysis.get("time_context")

        if time_context is not None:
            time_context = str(time_context).strip()
            if not time_context:
                time_context = None

        scope = str(
            analysis.get("memory_scope", "KEINE")
        ).strip()

        if scope not in self.MEMORY_SCOPES:
            scope = "KEINE"

        # Sicherheitsregel: KEINE darf keine Memory-Daten auslösen.
        if action == "KEINE":
            category = ""
            memory_type = ""
            entity_type = ""
            information = ""
            time_context = None

        # NEU braucht eine vollständige Information.
        if action == "NEU":
            if not (category and memory_type and information):
                action = "KEINE"

        # AENDERN braucht ein Suchziel.
        if action == "AENDERN":
            if not search_target:
                action = "KEINE"

        # LOESCHEN braucht ein Suchziel.
        if action == "LOESCHEN":
            if not search_target:
                action = "KEINE"

        return {
            "action": action,
            "search_target": search_target,
            "category": category,
            "memory_type": memory_type,
            "entity_type": entity_type,
            "information": information,
            "time_context": time_context,
            "memory_scope": scope,
        }

    # ============================================================
    # LEERE ANALYSE
    # ============================================================

    @staticmethod
    def _empty_analysis() -> Dict[str, Any]:
        return {
            "action": "KEINE",
            "search_target": "",
            "category": "",
            "memory_type": "",
            "entity_type": "",
            "information": "",
            "time_context": None,
            "memory_scope": "KEINE",
        }

    # ============================================================
    # MEMORY VERARBEITEN
    # ============================================================

    def process_memory(
        self,
        analysis: Dict[str, Any]
    ):
        action = analysis["action"]

        if action == "KEINE":
            return

        if action == "NEU":
            try:
                saved = self.memory.save(
                    category=analysis["category"],
                    memory_type=analysis["memory_type"],
                    entity_type=analysis["entity_type"],
                    information=analysis["information"],
                    time_context=analysis["time_context"],
                )

                if saved:
                    print(
                        "[MEMORY] Gespeichert: "
                        f"{analysis['category']} | "
                        f"{analysis['memory_type']} | "
                        f"{analysis['entity_type'] or 'Unbekannt'} | "
                        f"{analysis['information']}"
                    )
                else:
                    print(
                        "[MEMORY] Bereits vorhanden: "
                        f"{analysis['information']}"
                    )

            except Exception as error:
                print(f"[ERROR] Memory konnte nicht gespeichert werden: {error}")
                self.state.record_error(str(error))

            self.state.update_memory_count(self.memory.count())
            return

        if action == "LOESCHEN":
            self._delete_memory(analysis["search_target"])
            self.state.update_memory_count(self.memory.count())
            return

        if action == "AENDERN":
            self._update_memory(analysis)
            self.state.update_memory_count(self.memory.count())
            return

    # ============================================================
    # MEMORY LÖSCHEN
    # ============================================================

    def _delete_memory(
        self,
        search_target: str
    ):
        candidates = self.memory.search_candidates(
            information=search_target,
            limit=10
        )

        if not candidates:
            print(f"[MEMORY] Nicht gefunden: {search_target}")
            return

        target_normalized = self.memory._normalize(search_target)
        selected = None

        for candidate in candidates:
            candidate_information = candidate[4]
            if self.memory._normalize(candidate_information) == target_normalized:
                selected = candidate
                break

        if selected is None:
            if len(candidates) == 1:
                selected = candidates[0]
            else:
                print(
                    "[MEMORY] Mehrere mögliche Treffer gefunden. "
                    f"Löschen abgebrochen: {search_target}"
                )
                return

        memory_id = selected[0]
        deleted = self.memory.delete(memory_id)

        if deleted:
            print(f"[MEMORY] Gelöscht: {selected[4]}")
        else:
            print(f"[MEMORY] Löschen fehlgeschlagen: {selected[4]}")

    # ============================================================
    # MEMORY ÄNDERN
    # ============================================================

    def _update_memory(
        self,
        analysis: Dict[str, Any]
    ):
        target = analysis["search_target"]

        candidates = self.memory.search_candidates(
            information=target,
            category=analysis["category"] or None,
            limit=10
        )

        if not candidates:
            candidates = self.memory.search_candidates(
                information=target,
                limit=10
            )

        if not candidates:
            print(f"[MEMORY] Keine passende Memory gefunden: {target}")
            return

        target_normalized = self.memory._normalize(target)
        selected = None

        for candidate in candidates:
            if self.memory._normalize(candidate[4]) == target_normalized:
                selected = candidate
                break

        if selected is None:
            if len(candidates) == 1:
                selected = candidates[0]
            else:
                print(f"[MEMORY] Änderung nicht eindeutig genug: {target}")
                return

        memory_id = selected[0]
        old_category = selected[1]
        old_memory_type = selected[2]
        old_entity_type = selected[3]
        old_information = selected[4]
        old_time_context = selected[5]

        new_category = analysis["category"] or old_category
        new_memory_type = analysis["memory_type"] or old_memory_type
        new_entity_type = analysis["entity_type"] or old_entity_type
        new_information = analysis["information"] or old_information
        new_time_context = (
            analysis["time_context"]
            if analysis["time_context"] is not None
            else old_time_context
        )

        try:
            updated = self.memory.update(
                memory_id=memory_id,
                category=new_category,
                memory_type=new_memory_type,
                entity_type=new_entity_type,
                information=new_information,
                time_context=new_time_context,
            )

            if updated:
                print(f"[MEMORY] Geändert: {old_information} → {new_information}")
            else:
                print("[MEMORY] Änderung fehlgeschlagen.")

        except Exception as error:
            print(f"[ERROR] Memory konnte nicht geändert werden: {error}")
            self.state.record_error(str(error))

    # ============================================================
    # RELEVANTE MEMORY LADEN
    # ============================================================

    def get_relevant_memories(
        self,
        analysis: Dict[str, Any]
    ) -> List[tuple]:
        scope = analysis["memory_scope"]

        if scope == "KEINE":
            return []

        if scope == "ALLE":
            return self.memory.get_all()

        return self.memory.get_by_category(scope)

    # ============================================================
    # MEMORY TEXT ERSTELLEN
    # ============================================================

    @staticmethod
    def build_memory_text(memories) -> str:
        if not memories:
            return "Keine relevanten gespeicherten Informationen."

        lines = []
        for (category, memory_type, entity_type, information, time_context) in memories:
            line = (
                f"- Kategorie: {category} | "
                f"Typ: {memory_type} | "
                f"Objekttyp: {entity_type or 'Unbekannt'} | "
                f"Information: {information}"
            )
            if time_context:
                line += f" | Zeit: {time_context}"
            lines.append(line)

        return "\n".join(lines)

    # ============================================================
    # SYSTEM-PROMPT
    # ============================================================

    def build_system_prompt(self, memory_text: str) -> str:
        return build_system_prompt(memory_text, user_name="Joel")

    # ============================================================
    # ANTWORT
    # ============================================================

    def generate_response(
        self,
        message: str,
        analysis: Dict[str, Any],
        memories
    ) -> str:
        memory_text = self.build_memory_text(memories)
        system_prompt = self.build_system_prompt(memory_text)
        recent_history = self.context.get_recent_history()

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(recent_history)

        try:
            answer = self.model_manager.chat(
                messages=messages,
                task_type=TaskType.CHAT,
                json_mode=False
            )
            return answer.strip()

        except Exception as error:
            print(f"[ERROR] Antwort konnte nicht erzeugt werden: {error}")
            self.state.record_error(str(error))
            return (
                "Entschuldigung, Sir. "
                "Mein lokales Sprachmodell "
                "ist momentan nicht erreichbar."
            )

    # ============================================================
    # HAUPTMETHODE
    # ============================================================

    def respond(self, message: str) -> str:
        message = message.strip()

        if not message:
            return "Wie kann ich Ihnen helfen, Sir?"

        # 1. Benutzer-Nachricht im Kurzzeitgedächtnis
        self.context.add_user_message(message)

        # 2. EIN Analyzer-Call
        analysis = self.analyze_message(message)
        print(f"[ANALYSE] {analysis}")

        # 3. Memory-Aktion ausführen
        self.process_memory(analysis)

        # 4. Relevante Memories laden
        memories = self.get_relevant_memories(analysis)

        # 5. EIN Response-Call
        answer = self.generate_response(
            message=message,
            analysis=analysis,
            memories=memories,
        )

        # 6. Antwort speichern
        self.context.add_assistant_message(answer)

        return answer

    # ============================================================
    # MEMORY AUSLESEN
    # ============================================================

    def get_all_memories(self):
        return self.memory.get_all()

    # ============================================================
    # MEMORY ANZAHL
    # ============================================================

    def memory_count(self):
        return self.memory.count()

    # ============================================================
    # BEENDEN
    # ============================================================

    def close(self):
        self.memory.close()