"""
JARVIS Spracherkennung

Lokale, kostenlose Engines in dieser Reihenfolge:

    1. faster-whisper – schnell, sehr genau, läuft offline
    2. openai-whisper – Referenzimplementierung, offline
    3. vosk           – sehr genügsam, offline

Alle Engines sind optional. Ist keine installiert, meldet JARVIS das
verständlich und bleibt über die Tastatur bedienbar.
"""

import json
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.config import config
from src.utils.logging import STT, get_logger
from src.voice.audio import Recording

logger = get_logger(STT)


class STTEngine(ABC):
    name = ""

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def transcribe(self, recording: Recording) -> str:
        ...


def _to_wave(recording: Recording) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        path = Path(handle.name)

    return recording.save(path)


class FasterWhisperEngine(STTEngine):
    name = "faster_whisper"

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings if settings is not None else config.section("voice")
        self.model_size = str(self.settings.get("whisper_model", "base"))
        self._model = None

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self):
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel

        self._model = WhisperModel(self.model_size, device="auto", compute_type="int8")
        return self._model

    def transcribe(self, recording: Recording) -> str:
        path = _to_wave(recording)

        try:
            segments, _ = self._load().transcribe(str(path), language="de")
            return " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            path.unlink(missing_ok=True)


class WhisperEngine(STTEngine):
    name = "whisper"

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings if settings is not None else config.section("voice")
        self.model_size = str(self.settings.get("whisper_model", "base"))
        self._model = None

    def is_available(self) -> bool:
        try:
            import whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self):
        if self._model is not None:
            return self._model

        import whisper

        self._model = whisper.load_model(self.model_size)
        return self._model

    def transcribe(self, recording: Recording) -> str:
        path = _to_wave(recording)

        try:
            result = self._load().transcribe(str(path), language="de")
            return str(result.get("text", "")).strip()
        finally:
            path.unlink(missing_ok=True)


class VoskEngine(STTEngine):
    name = "vosk"

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings if settings is not None else config.section("voice")
        self.model_path = str(self.settings.get("vosk_model", ""))
        self._model = None

    def is_available(self) -> bool:
        if not self.model_path or not Path(self.model_path).exists():
            return False

        try:
            import vosk  # noqa: F401

            return True
        except ImportError:
            return False

    def transcribe(self, recording: Recording) -> str:
        from vosk import KaldiRecognizer, Model

        if self._model is None:
            self._model = Model(self.model_path)

        recognizer = KaldiRecognizer(self._model, recording.sample_rate)
        recognizer.AcceptWaveform(recording.data)

        result = json.loads(recognizer.FinalResult())
        return str(result.get("text", "")).strip()


ENGINES: Dict[str, type] = {
    FasterWhisperEngine.name: FasterWhisperEngine,
    WhisperEngine.name: WhisperEngine,
    VoskEngine.name: VoskEngine,
}


class Transcriber:
    """Wandelt eine Aufnahme in Text um."""

    def __init__(
        self,
        engine: Optional[STTEngine] = None,
        settings: Optional[Dict[str, Any]] = None,
    ):
        self.settings = settings if settings is not None else config.section("voice")
        self.enabled = bool(self.settings.get("stt_enabled", True))
        self.engine = engine or self._select_engine()

    def _select_engine(self) -> Optional[STTEngine]:
        preferred = str(self.settings.get("stt_engine", "auto")).lower()

        if preferred in ENGINES:
            candidates: List[STTEngine] = [ENGINES[preferred](settings=self.settings)]
        else:
            candidates = [
                FasterWhisperEngine(settings=self.settings),
                WhisperEngine(settings=self.settings),
                VoskEngine(settings=self.settings),
            ]

        for candidate in candidates:
            if candidate.is_available():
                logger.info(f"Spracherkennung: {candidate.name}")
                return candidate

        logger.warning(
            "Keine Spracherkennung gefunden. "
            "Empfehlung: pip install faster-whisper"
        )
        return None

    @property
    def available(self) -> bool:
        return self.enabled and self.engine is not None

    def transcribe(self, recording: Optional[Recording]) -> str:
        if recording is None or not self.available or self.engine is None:
            return ""

        if recording.seconds < 0.3:
            logger.info("Aufnahme zu kurz.")
            return ""

        try:
            text = self.engine.transcribe(recording)
        except Exception as error:
            logger.error(f"Spracherkennung fehlgeschlagen: {error}")
            return ""

        logger.info(f"Erkannt: {text}")
        return text
