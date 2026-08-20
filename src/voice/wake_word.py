"""
JARVIS Wake Word

Erkennung des Aktivierungsworts im erkannten Text ("Jarvis", "Hey Jarvis").
Die Prüfung ist tolerant gegenüber Erkennungsfehlern der Spracherkennung
(z. B. "Jervis", "Charvis") und entfernt das Wort aus dem Befehl.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional, Sequence, Tuple

from src.memory.search import normalize
from src.utils.logging import VOICE, get_logger

logger = get_logger(VOICE)

DEFAULT_WAKE_WORDS: Tuple[str, ...] = ("jarvis", "hey jarvis", "ok jarvis")

MIN_SIMILARITY = 0.8


@dataclass(frozen=True)
class WakeWordMatch:
    detected: bool
    command: str = ""


class WakeWordDetector:
    """Prüft, ob ein Satz mit dem Aktivierungswort beginnt."""

    def __init__(self, wake_words: Optional[Sequence[str]] = None):
        self.wake_words = tuple(
            normalize(word) for word in (wake_words or DEFAULT_WAKE_WORDS)
        )

    def detect(self, text: str) -> WakeWordMatch:
        normalized = normalize(text)

        if not normalized:
            return WakeWordMatch(detected=False)

        for wake_word in sorted(self.wake_words, key=len, reverse=True):
            if normalized.startswith(wake_word):
                return WakeWordMatch(
                    detected=True,
                    command=self._strip(text, len(wake_word.split())),
                )

        words = normalized.split()

        if words and any(
            SequenceMatcher(None, words[0], wake_word.split()[-1]).ratio() >= MIN_SIMILARITY
            for wake_word in self.wake_words
        ):
            return WakeWordMatch(detected=True, command=self._strip(text, 1))

        return WakeWordMatch(detected=False)

    @staticmethod
    def _strip(text: str, word_count: int) -> str:
        remainder = " ".join(text.strip().split()[word_count:])
        return re.sub(r"^[,.;:!?\s]+", "", remainder).strip()
