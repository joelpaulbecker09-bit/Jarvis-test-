"""
JARVIS Sprachausgabe

Mehrere austauschbare, lokale Engines. Es wird die erste genommen, die auf
diesem Rechner tatsächlich vorhanden ist:

    1. Piper       – beste deutsche Qualität, lokal, kostenlos
    2. pyttsx3     – Systemstimme (SAPI5 unter Windows, espeak unter Linux)
    3. espeak-ng   – Rückfalllösung über die Kommandozeile

Ist keine Engine vorhanden, wird die Antwort nur protokolliert. JARVIS
bleibt in jedem Fall bedienbar.
"""

import shutil
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.config import config
from src.utils.logging import TTS, get_logger

logger = get_logger(TTS)


class TTSEngine(ABC):
    """Gemeinsame Schnittstelle aller Sprachausgaben."""

    name = ""

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def speak(self, text: str) -> bool:
        """Spricht den Text. Gibt True zurück, wenn es funktioniert hat."""

    def stop(self) -> None:
        """Bricht die laufende Ausgabe ab, sofern die Engine das kann."""


class PiperEngine(TTSEngine):
    """
    Piper: lokale neuronale Stimme.

    Erwartet das Programm 'piper' im PATH und ein deutsches Stimmmodell
    (config: voice.piper_model).
    """

    name = "piper"

    def __init__(self, model_path: str = "", settings: Optional[Dict[str, Any]] = None):
        self.settings = settings if settings is not None else config.section("voice")
        self.model_path = model_path or str(self.settings.get("piper_model", ""))
        self._process: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        if not self.model_path:
            return False

        return shutil.which("piper") is not None and Path(self.model_path).exists()

    def speak(self, text: str) -> bool:
        if not self.is_available():
            return False

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wave_path = Path(handle.name)

        try:
            subprocess.run(
                ["piper", "--model", self.model_path, "--output_file", str(wave_path)],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=120,
                check=True,
            )
            return _play_wave(wave_path)
        except (subprocess.SubprocessError, OSError) as error:
            logger.warning(f"Piper fehlgeschlagen: {error}")
            return False
        finally:
            wave_path.unlink(missing_ok=True)


class Pyttsx3Engine(TTSEngine):
    """Systemstimme über pyttsx3 (offline, plattformübergreifend)."""

    name = "pyttsx3"

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings if settings is not None else config.section("voice")
        self._engine = None

    def _load(self):
        if self._engine is not None:
            return self._engine

        try:
            import pyttsx3
        except ImportError:
            return None

        try:
            engine = pyttsx3.init()
        except Exception as error:
            logger.warning(f"pyttsx3 nicht initialisierbar: {error}")
            return None

        engine.setProperty("rate", int(self.settings.get("voice_rate", 165)))

        for voice in engine.getProperty("voices"):
            identifier = f"{voice.id} {getattr(voice, 'name', '')}".lower()
            if "german" in identifier or "de_" in identifier or "de-" in identifier:
                engine.setProperty("voice", voice.id)
                break

        self._engine = engine
        return engine

    def is_available(self) -> bool:
        return self._load() is not None

    def speak(self, text: str) -> bool:
        engine = self._load()

        if engine is None:
            return False

        try:
            engine.say(text)
            engine.runAndWait()
            return True
        except Exception as error:
            logger.warning(f"pyttsx3 fehlgeschlagen: {error}")
            return False

    def stop(self) -> None:
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass


class EspeakEngine(TTSEngine):
    """Rückfalllösung: espeak-ng mit deutscher Stimme."""

    name = "espeak"

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings if settings is not None else config.section("voice")
        self._process: Optional[subprocess.Popen] = None

    def _executable(self) -> Optional[str]:
        return shutil.which("espeak-ng") or shutil.which("espeak")

    def is_available(self) -> bool:
        return self._executable() is not None

    def speak(self, text: str) -> bool:
        executable = self._executable()

        if executable is None:
            return False

        words_per_minute = int(self.settings.get("voice_rate", 165))

        try:
            self._process = subprocess.Popen(
                [executable, "-v", "de", "-s", str(words_per_minute), text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._process.wait(timeout=120)
            return self._process.returncode == 0
        except (subprocess.SubprocessError, OSError) as error:
            logger.warning(f"espeak fehlgeschlagen: {error}")
            return False

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()


def _play_wave(path: Path) -> bool:
    """Spielt eine WAV-Datei mit dem ersten verfügbaren Systemplayer ab."""
    for player in ("aplay", "paplay", "afplay"):
        executable = shutil.which(player)
        if executable:
            result = subprocess.run(
                [executable, str(path)],
                capture_output=True,
                timeout=180,
            )
            return result.returncode == 0

    try:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return True
    except Exception:
        logger.warning("Keine Möglichkeit gefunden, die Audiodatei abzuspielen.")
        return False


ENGINES: Dict[str, type] = {
    PiperEngine.name: PiperEngine,
    Pyttsx3Engine.name: Pyttsx3Engine,
    EspeakEngine.name: EspeakEngine,
}


class Speaker:
    """
    Sprachausgabe von JARVIS.

    Wählt automatisch die beste verfügbare Engine oder verwendet die in
    config.voice.tts_engine festgelegte.
    """

    def __init__(self, engine: Optional[TTSEngine] = None, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings if settings is not None else config.section("voice")
        self.enabled = bool(self.settings.get("tts_enabled", True))
        self.engine = engine or self._select_engine()
        self._thread: Optional[threading.Thread] = None

    def _select_engine(self) -> Optional[TTSEngine]:
        preferred = str(self.settings.get("tts_engine", "auto")).lower()

        if preferred in ENGINES:
            candidates: List[TTSEngine] = [ENGINES[preferred](settings=self.settings)]
        else:
            candidates = [
                PiperEngine(settings=self.settings),
                Pyttsx3Engine(settings=self.settings),
                EspeakEngine(settings=self.settings),
            ]

        for candidate in candidates:
            if candidate.is_available():
                logger.info(f"Sprachausgabe: {candidate.name}")
                return candidate

        logger.warning(
            "Keine Sprachausgabe gefunden. "
            "Empfehlung: pip install pyttsx3 oder Piper installieren."
        )
        return None

    @property
    def available(self) -> bool:
        return self.enabled and self.engine is not None

    def speak(self, text: str) -> bool:
        text = text.strip()

        if not text or not self.available:
            return False

        return bool(self.engine and self.engine.speak(text))

    def speak_async(self, text: str) -> None:
        """Spricht im Hintergrund, damit die Oberfläche flüssig bleibt."""
        if not self.available:
            return

        self._thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self.engine is not None:
            self.engine.stop()
