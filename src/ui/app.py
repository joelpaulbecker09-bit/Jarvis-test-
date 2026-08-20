"""
JARVIS Anwendung

Verbindet Oberfläche, Denkleistung (Brain) und Sprache:

    Fenster  ─ Text/Mikrofon ─►  Warteschlange
                                     │
                              Arbeits-Thread
                                     │
                        Brain ─► Antwort ─► Sprachausgabe
                                     │
                              Fenster (Verlauf, Zustand)

Die Oberfläche bleibt bedienbar, während JARVIS denkt oder spricht, weil
alle langsamen Schritte in einem eigenen Thread laufen.
"""

import queue
import threading
from tkinter import messagebox
from typing import Optional

from config.config import config
from src.core.brain import JarvisBrain
from src.core.state import AssistantState
from src.ui.window import JarvisWindow
from src.utils.logging import UI, get_logger
from src.voice.audio import Microphone, Recording
from src.voice.stt import Transcriber
from src.voice.tts import Speaker
from src.voice.wake_word import WakeWordDetector

logger = get_logger(UI)


class JarvisApp:
    """Zusammenspiel von Oberfläche, Brain und Sprache."""

    def __init__(self, brain: Optional[JarvisBrain] = None):
        ui_settings = config.section("ui")

        self.brain = brain or JarvisBrain(confirm_handler=self._confirm)
        self.speaker = Speaker()
        self.transcriber = Transcriber()
        self.microphone = Microphone(on_level=self._on_level)
        self.wake_word = WakeWordDetector(
            wake_words=[str(config.section("voice").get("wake_word", "jarvis"))]
        )

        self.window = JarvisWindow(
            on_text=self.submit,
            on_listen_start=self.start_listening,
            on_listen_stop=self.stop_listening,
            particle_count=int(ui_settings.get("particle_count", 420)),
        )

        self._messages: "queue.Queue[str]" = queue.Queue()
        self._running = True
        self._worker = threading.Thread(target=self._work, daemon=True)
        self._worker.start()

    # ------------------------------------------------------------
    # Eingaben aus der Oberfläche
    # ------------------------------------------------------------

    def submit(self, message: str) -> None:
        self._set_state(AssistantState.THINKING)
        self._messages.put(message)

    def start_listening(self) -> None:
        if not self.microphone.is_available():
            self._show("JARVIS", "Kein Mikrofon verfügbar. Bitte tippen Sie, Sir.")
            self._set_state(AssistantState.IDLE)
            return

        if not self.transcriber.available:
            self._show(
                "JARVIS",
                "Keine Spracherkennung installiert (pip install faster-whisper).",
            )
            self._set_state(AssistantState.IDLE)
            return

        if self.microphone.start():
            self._set_state(AssistantState.LISTENING)

    def stop_listening(self) -> None:
        recording = self.microphone.stop()
        self._set_state(AssistantState.THINKING)

        threading.Thread(
            target=self._transcribe_and_submit,
            args=(recording,),
            daemon=True,
        ).start()

    def _transcribe_and_submit(self, recording: Optional[Recording]) -> None:
        text = self.transcriber.transcribe(recording)

        if not text:
            self._show("JARVIS", "Ich habe nichts verstanden, Sir.")
            self._set_state(AssistantState.IDLE)
            return

        # Vorangestelltes "Jarvis, ..." gehört nicht zum Befehl.
        match = self.wake_word.detect(text)
        if match.detected and match.command:
            text = match.command

        self._show("Sie", text)
        self._messages.put(text)

    # ------------------------------------------------------------
    # Verarbeitung
    # ------------------------------------------------------------

    def _work(self) -> None:
        while self._running:
            try:
                message = self._messages.get(timeout=0.2)
            except queue.Empty:
                continue

            self._set_state(AssistantState.THINKING)

            try:
                answer = self.brain.respond(message)
            except Exception as error:
                logger.error(f"Verarbeitung fehlgeschlagen: {error}")
                answer = "Es ist ein Fehler aufgetreten, Sir."
                self._set_state(AssistantState.ERROR)

            self._show("JARVIS", answer)

            if self.speaker.available:
                self._set_state(AssistantState.SPEAKING)
                self.speaker.speak(answer)

            self._set_state(AssistantState.IDLE)

    def _confirm(self, question: str) -> bool:
        """Rückfrage bei heiklen Aktionen, im Tk-Thread gestellt."""
        result = {"value": False}
        done = threading.Event()

        def show() -> None:
            result["value"] = bool(messagebox.askyesno("JARVIS", question))
            done.set()

        self.window.root.after(0, show)
        done.wait(timeout=120)
        return result["value"]

    # ------------------------------------------------------------
    # Ausgaben an die Oberfläche (immer im Tk-Thread)
    # ------------------------------------------------------------

    def _show(self, speaker: str, text: str) -> None:
        self.window.root.after(0, lambda: self.window.add_transcript(speaker, text))

    def _set_state(self, state: AssistantState) -> None:
        self.brain.state.set_mode(state)
        self.window.root.after(0, lambda: self.window.set_state(state))

    def _on_level(self, level: float) -> None:
        self.window.root.after(0, lambda: self.window.set_audio_level(level))

    # ------------------------------------------------------------
    # Lebenszyklus
    # ------------------------------------------------------------

    def run(self) -> None:
        self._show("JARVIS", "Systeme bereit, Sir.")

        try:
            self.window.run()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._running = False
        self.speaker.stop()
        self.brain.close()


def main() -> None:
    JarvisApp().run()


if __name__ == "__main__":
    main()
