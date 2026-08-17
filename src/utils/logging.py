"""
JARVIS Logging

Einheitliche Ausgabe mit festen Kanälen ([CORE], [MEMORY], [TOOL], ...).
Alle Module verwenden ausschließlich diese Logger, nie print().
"""

import logging
import sys
from pathlib import Path
from typing import Optional

CORE = "CORE"
MEMORY = "MEMORY"
LLM = "LLM"
VOICE = "VOICE"
STT = "STT"
TTS = "TTS"
TOOL = "TOOL"
WEB = "WEB"
UI = "UI"

_CONFIGURED = False


class _ChannelFormatter(logging.Formatter):
    """Formatiert Meldungen als '[KANAL] Text' bzw. '[KANAL] [ERROR] Text'."""

    def format(self, record: logging.LogRecord) -> str:
        channel = record.name.split(".")[-1].upper()
        message = record.getMessage()

        if record.levelno >= logging.ERROR:
            line = f"[{channel}] [ERROR] {message}"
        elif record.levelno >= logging.WARNING:
            line = f"[{channel}] [WARNUNG] {message}"
        else:
            line = f"[{channel}] {message}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """
    Richtet das Logging einmalig ein.

    Args:
        level: Log-Level als Text ("DEBUG", "INFO", "WARNING", "ERROR").
        log_file: Optionale Datei, in die zusätzlich geschrieben wird.
    """
    global _CONFIGURED

    root = logging.getLogger("jarvis")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False

    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(_ChannelFormatter())
    root.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(channel: str) -> logging.Logger:
    """
    Liefert den Logger eines Kanals, z. B. get_logger(MEMORY).
    """
    if not _CONFIGURED:
        setup_logging()

    return logging.getLogger(f"jarvis.{channel.lower()}")
