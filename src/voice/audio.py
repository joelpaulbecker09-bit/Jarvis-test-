"""
JARVIS Audio-Aufnahme

Mikrofonaufnahme über sounddevice (bevorzugt) oder das Standardpaket
PyAudio. Beide sind optional: fehlt beides, meldet JARVIS das klar und
bleibt per Tastatur bedienbar.

Der gemessene Pegel (0.0 bis 1.0) treibt später die Partikel-Animation.
"""

import audioop
import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from config.config import config
from src.utils.logging import VOICE, get_logger

logger = get_logger(VOICE)

LevelCallback = Callable[[float], None]

SAMPLE_WIDTH = 2  # 16 Bit


@dataclass
class Recording:
    """Aufgenommenes Audio als PCM-Rohdaten."""

    data: bytes
    sample_rate: int

    @property
    def seconds(self) -> float:
        return len(self.data) / (self.sample_rate * SAMPLE_WIDTH)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(SAMPLE_WIDTH)
            handle.setframerate(self.sample_rate)
            handle.writeframes(self.data)

        return path


def level_of(chunk: bytes) -> float:
    """Lautstärke eines Blocks als Wert zwischen 0.0 und 1.0."""
    if not chunk:
        return 0.0

    rms = audioop.rms(chunk, SAMPLE_WIDTH)

    # logarithmische Skala, damit leise Sprache sichtbar bleibt
    return min(1.0, math.log10(1 + rms) / math.log10(1 + 32768))


class Microphone:
    """
    Mikrofon mit Push-to-Talk-Aufnahme.

    Verwendung:

        microphone = Microphone()
        microphone.start()
        ...
        recording = microphone.stop()
    """

    def __init__(
        self,
        sample_rate: Optional[int] = None,
        on_level: Optional[LevelCallback] = None,
    ):
        settings = config.section("voice")
        self.sample_rate = sample_rate or int(settings.get("sample_rate", 16000))
        self.max_seconds = int(settings.get("max_record_seconds", 30))
        self.on_level = on_level
        self.block_size = 1024

        self._frames: List[bytes] = []
        self._stream = None
        self._backend = ""
        self._pyaudio = None

    # ------------------------------------------------------------
    # Verfügbarkeit
    # ------------------------------------------------------------

    def is_available(self) -> bool:
        return self._detect_backend() != ""

    def _detect_backend(self) -> str:
        try:
            import sounddevice  # noqa: F401

            return "sounddevice"
        except (ImportError, OSError):
            pass

        try:
            import pyaudio  # noqa: F401

            return "pyaudio"
        except ImportError:
            return ""

    # ------------------------------------------------------------
    # Aufnahme
    # ------------------------------------------------------------

    def start(self) -> bool:
        backend = self._detect_backend()

        if not backend:
            logger.warning(
                "Kein Mikrofon-Backend gefunden. "
                "Empfehlung: pip install sounddevice"
            )
            return False

        self._frames = []
        self._backend = backend

        if backend == "sounddevice":
            import sounddevice

            def callback(indata, frames, time_info, status) -> None:
                chunk = bytes(indata)
                self._frames.append(chunk)

                if self.on_level is not None:
                    self.on_level(level_of(chunk))

            self._stream = sounddevice.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="int16",
                channels=1,
                callback=callback,
            )
            self._stream.start()
            return True

        import pyaudio

        self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.block_size,
        )
        return True

    def read_chunk(self) -> None:
        """Nur für PyAudio nötig: einen Block einlesen."""
        if self._backend != "pyaudio" or self._stream is None:
            return

        chunk = self._stream.read(self.block_size, exception_on_overflow=False)
        self._frames.append(chunk)

        if self.on_level is not None:
            self.on_level(level_of(chunk))

    def stop(self) -> Optional[Recording]:
        if self._stream is None:
            return None

        try:
            if self._backend == "sounddevice":
                self._stream.stop()
                self._stream.close()
            else:
                self._stream.stop_stream()
                self._stream.close()
                if self._pyaudio is not None:
                    self._pyaudio.terminate()
                    self._pyaudio = None
        finally:
            self._stream = None

        data = b"".join(self._frames)
        self._frames = []

        if self.on_level is not None:
            self.on_level(0.0)

        if not data:
            return None

        return Recording(data=data, sample_rate=self.sample_rate)
