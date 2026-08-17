"""
JARVIS Memory Search

Robuste Suche über die Langzeit-Memory.

Die SQLite-Schicht liefert Kandidaten (exakt, Teilstring, Kategorie);
diese Schicht bewertet sie und entscheidet, ob ein Treffer eindeutig ist.

Bewertet wird eine Kombination aus:
- exakter Übereinstimmung
- Präfix-/Teilstring-Übereinstimmung
- Wortüberschneidung
- Ähnlichkeit (Tippfehlertoleranz über difflib)
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, List, Optional, Sequence

from src.memory.models import MemoryEntry

_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)

# Häufige deutsche Füllwörter, die eine Suche nur verwässern.
_STOPWORDS_RAW = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
    "eines", "und", "oder", "ich", "du", "er", "sie", "es", "wir", "ihr",
    "mein", "meine", "meinen", "meiner", "meines", "mich", "mir", "dass",
    "nicht", "mehr", "an", "am", "in", "im", "auf", "von", "vom", "zu", "zum",
    "zur", "mit", "für", "über", "was", "wer", "wie", "welche", "welches",
    "welcher", "ist", "sind", "war", "habe", "hab", "hat", "bin", "bist",
    "weißt", "weiss", "du", "vergiss", "lösch", "lösche", "löschen", "merke",
    "erinnere", "gerne", "gern", "sehr", "auch", "noch", "mal",
}


# Deutsche Sonderzeichen werden ausgeschrieben, damit "Grüße" und
# "Gruesse" als dasselbe gelten.
UMLAUTS = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
}


def normalize(value: Optional[str]) -> str:
    """Kleinschreibung, kollabierte Leerzeichen, Umlaute ausgeschrieben."""
    if value is None:
        return ""

    text = str(value).strip().lower()

    for umlaut, replacement in UMLAUTS.items():
        text = text.replace(umlaut, replacement)

    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.split())


# In derselben Schreibweise wie die zu vergleichenden Wörter.
STOPWORDS = {normalize(word) for word in _STOPWORDS_RAW}


def tokenize(value: Optional[str], drop_stopwords: bool = True) -> List[str]:
    """Zerlegt Text in vergleichbare Wörter."""
    words = _WORD_PATTERN.findall(normalize(value))

    if drop_stopwords:
        filtered = [word for word in words if word not in STOPWORDS]
        if filtered:
            return filtered

    return words


def similarity(left: str, right: str) -> float:
    """Ähnlichkeit zweier Texte zwischen 0.0 und 1.0."""
    if not left or not right:
        return 0.0

    return SequenceMatcher(None, left, right).ratio()


def score_entry(entry: MemoryEntry, query: str) -> float:
    """
    Bewertet, wie gut ein Memory-Eintrag zu einer Suchanfrage passt.

    1.0  exakte Übereinstimmung der Information
    0.0  kein erkennbarer Bezug
    """
    query_normalized = normalize(query)

    if not query_normalized:
        return 0.0

    information = normalize(entry.information)

    if information == query_normalized:
        return 1.0

    best = 0.0

    if information.startswith(query_normalized) or query_normalized.startswith(information):
        best = max(best, 0.9)

    if query_normalized in information or information in query_normalized:
        best = max(best, 0.8)

    query_tokens = set(tokenize(query))
    information_tokens = set(tokenize(entry.information, drop_stopwords=False))

    if query_tokens and information_tokens:
        overlap = query_tokens & information_tokens
        if overlap:
            coverage = len(overlap) / len(information_tokens | query_tokens)
            best = max(best, 0.55 + 0.3 * coverage)

    best = max(best, 0.85 * similarity(information, query_normalized))

    # Kategorie/Objekttyp helfen bei Fragen wie "meine Bands".
    for attribute in (entry.category, entry.entity_type, entry.memory_type):
        if attribute and normalize(attribute) in query_tokens:
            best = max(best, 0.5)

    return round(min(best, 1.0), 4)


@dataclass(frozen=True)
class ScoredMemory:
    entry: MemoryEntry
    score: float


@dataclass(frozen=True)
class MatchResult:
    """Ergebnis einer Suche nach genau einem gemeinten Eintrag."""

    best: Optional[MemoryEntry]
    ambiguous: bool
    candidates: Sequence[ScoredMemory]

    @property
    def found(self) -> bool:
        return self.best is not None


def rank(
    entries: Iterable[MemoryEntry],
    query: str,
    min_score: float = 0.55,
    limit: int = 10,
) -> List[ScoredMemory]:
    """Sortiert Einträge nach Relevanz zur Suchanfrage."""
    scored = [
        ScoredMemory(entry=entry, score=score_entry(entry, query))
        for entry in entries
    ]

    relevant = [item for item in scored if item.score >= min_score]
    relevant.sort(key=lambda item: item.score, reverse=True)

    return relevant[:limit]


def resolve_single(
    entries: Iterable[MemoryEntry],
    query: str,
    min_score: float = 0.55,
    decisive_margin: float = 0.12,
) -> MatchResult:
    """
    Bestimmt den einen gemeinten Eintrag.

    Eindeutig ist ein Treffer, wenn er exakt passt oder deutlich besser
    bewertet ist als der zweitbeste Kandidat. Andernfalls gilt die Suche als
    mehrdeutig – JARVIS darf dann nichts löschen oder überschreiben.
    """
    candidates = rank(entries, query, min_score=min_score)

    if not candidates:
        return MatchResult(best=None, ambiguous=False, candidates=())

    best = candidates[0]

    if len(candidates) == 1 or best.score >= 1.0:
        return MatchResult(best=best.entry, ambiguous=False, candidates=candidates)

    if best.score - candidates[1].score >= decisive_margin:
        return MatchResult(best=best.entry, ambiguous=False, candidates=candidates)

    return MatchResult(best=None, ambiguous=True, candidates=candidates)
