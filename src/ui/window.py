"""
JARVIS Hauptfenster

Minimalistische, dunkle Oberfläche:

    - großer Partikel-Orb in der Mitte
    - darunter Uhrzeit und Datum
    - Statuszeile (Bereit / Ich höre zu / Ich denke nach / Ich spreche)
    - Verlauf der letzten Wortwechsel
    - Texteingabe und Mikrofon-Taste (Leertaste = Push-to-Talk)

Das Fenster kennt weder Modelle noch Werkzeuge. Es meldet Eingaben über
Rückrufe an die Anwendung und zeigt an, was ihm gesagt wird.
"""

import tkinter as tk
from datetime import datetime
from typing import Callable, List, Optional

from src.core.state import AssistantState
from src.ui.orb import OrbRenderer
from src.ui.states import BACKGROUND, FOREGROUND, MUTED, style_for, to_hex

WEEKDAYS = (
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
)

MONTHS = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)

FRAME_MILLISECONDS = 33  # rund 30 Bilder pro Sekunde
MAX_TRANSCRIPT_LINES = 8

TextCallback = Callable[[str], None]
VoidCallback = Callable[[], None]


def german_date(moment: datetime) -> str:
    weekday = WEEKDAYS[moment.weekday()]
    month = MONTHS[moment.month - 1]
    return f"{weekday}, {moment.day}. {month} {moment.year}".upper()


class JarvisWindow:
    """Fenster mit Orb, Uhr, Verlauf und Eingabe."""

    def __init__(
        self,
        on_text: Optional[TextCallback] = None,
        on_listen_start: Optional[VoidCallback] = None,
        on_listen_stop: Optional[VoidCallback] = None,
        particle_count: int = 420,
    ):
        self.on_text = on_text
        self.on_listen_start = on_listen_start
        self.on_listen_stop = on_listen_stop

        self.root = tk.Tk()
        self.root.title("JARVIS")
        self.root.configure(bg=BACKGROUND)
        self.root.geometry("1100x760")
        self.root.minsize(720, 560)

        self.canvas = tk.Canvas(
            self.root,
            bg=BACKGROUND,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.orb = OrbRenderer(self.canvas, particle_count=particle_count)
        self.state = AssistantState.IDLE
        self.transcript: List[str] = []
        self._listening = False
        self._last_frame = datetime.now()

        self._build_controls()
        self._bind_keys()

        self.root.after(FRAME_MILLISECONDS, self._tick)

    # ------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------

    def _build_controls(self) -> None:
        bar = tk.Frame(self.root, bg=BACKGROUND)
        bar.place(relx=0.5, rely=0.955, anchor="center", relwidth=0.72)

        self.entry = tk.Entry(
            bar,
            bg="#0d131c",
            fg=FOREGROUND,
            insertbackground=FOREGROUND,
            relief=tk.FLAT,
            font=("Helvetica", 12),
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=9, padx=(0, 10))
        self.entry.bind("<Return>", self._submit_text)

        self.mic_button = tk.Button(
            bar,
            text="Mikrofon",
            command=self.toggle_listening,
            bg="#12202f",
            fg=FOREGROUND,
            activebackground="#1b3047",
            activeforeground=FOREGROUND,
            relief=tk.FLAT,
            font=("Helvetica", 11),
            padx=18,
            pady=8,
        )
        self.mic_button.pack(side=tk.LEFT)

    def _bind_keys(self) -> None:
        self.root.bind("<Escape>", lambda event: self.close())
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<space>", self._space_pressed)

    def _toggle_fullscreen(self, event: Optional[tk.Event] = None) -> None:
        current = bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", not current)

    def _space_pressed(self, event: tk.Event) -> None:
        if self.root.focus_get() is self.entry:
            return

        self.toggle_listening()

    # ------------------------------------------------------------
    # Eingaben
    # ------------------------------------------------------------

    def _submit_text(self, event: Optional[tk.Event] = None) -> None:
        text = self.entry.get().strip()

        if not text:
            return

        self.entry.delete(0, tk.END)
        self.add_transcript("Sie", text)

        if self.on_text is not None:
            self.on_text(text)

    def toggle_listening(self) -> None:
        if self._listening:
            self._listening = False
            self.mic_button.configure(text="Mikrofon")

            if self.on_listen_stop is not None:
                self.on_listen_stop()
            return

        self._listening = True
        self.mic_button.configure(text="Aufnahme läuft")

        if self.on_listen_start is not None:
            self.on_listen_start()

    # ------------------------------------------------------------
    # Anzeige
    # ------------------------------------------------------------

    def set_state(self, state: AssistantState) -> None:
        self.state = state
        self.orb.set_state(state)

        if state != AssistantState.LISTENING and self._listening:
            self._listening = False
            self.mic_button.configure(text="Mikrofon")

    def set_audio_level(self, level: float) -> None:
        self.orb.set_audio_level(level)

    def add_transcript(self, speaker: str, text: str) -> None:
        for line in _wrap(f"{speaker}: {text}", 96):
            self.transcript.append(line)

        del self.transcript[:-MAX_TRANSCRIPT_LINES]

    def _tick(self) -> None:
        now = datetime.now()
        delta = (now - self._last_frame).total_seconds()
        self._last_frame = now

        self.orb.render(delta)
        self._draw_overlay(now)

        self.root.after(FRAME_MILLISECONDS, self._tick)

    def _draw_overlay(self, now: datetime) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        style = style_for(self.state)

        self.canvas.delete("overlay")

        clock_y = height * 0.5 + self.orb.sphere.radius * 1.55

        self.canvas.create_text(
            width / 2,
            clock_y,
            text=now.strftime("%H:%M"),
            fill=FOREGROUND,
            font=("Helvetica", 46, "bold"),
            tags="overlay",
        )

        self.canvas.create_text(
            width / 2,
            clock_y + 40,
            text=german_date(now),
            fill=MUTED,
            font=("Helvetica", 10),
            tags="overlay",
        )

        self.canvas.create_text(
            width / 2,
            height * 0.5 - self.orb.sphere.radius * 1.75,
            text=style.label.upper(),
            fill=to_hex(style.color),
            font=("Helvetica", 11, "bold"),
            tags="overlay",
        )

        for index, line in enumerate(self.transcript):
            self.canvas.create_text(
                30,
                30 + index * 20,
                text=line,
                fill=MUTED if line.startswith("Sie:") else FOREGROUND,
                font=("Helvetica", 10),
                anchor="w",
                tags="overlay",
            )

    # ------------------------------------------------------------
    # Lebenszyklus
    # ------------------------------------------------------------

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        self.root.destroy()


def _wrap(text: str, width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()

        if len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)

    return lines
