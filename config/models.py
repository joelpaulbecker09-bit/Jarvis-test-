"""
JARVIS Model Definitions & Tasks

Definiert verfügbare Modelle und deren Einsatzbereiche.
"""

from enum import Enum
from typing import Dict, Any


class TaskType(Enum):
    CHAT = "chat"
    ANALYSIS = "analysis"
    FAST = "fast"
    REASONING = "reasoning"
    VISION = "vision"


# Verfügbare Ollama-Modelle auf diesem System
AVAILABLE_MODELS = {
    "qwen3:8b": {
        "name": "qwen3:8b",
        "context_window": 8192,
        "role": "General Purpose / Chat / Analysis",
    },
    "gemma4:latest": {
        "name": "gemma4:latest",
        "context_window": 8192,
        "role": "Advanced Reasoning",
    },
    "gemma:2b": {
        "name": "gemma:2b",
        "context_window": 4096,
        "role": "Fast Lightweight Tasks",
    },
    "qwen3-vl:latest": {
        "name": "qwen3-vl:latest",
        "context_window": 8192,
        "role": "Vision & Multimodal Tasks",
    },
    "llama3:latest": {
        "name": "llama3:latest",
        "context_window": 8192,
        "role": "Fallback Chat",
    },
    "llama3.1:8b": {
        "name": "llama3.1:8b",
        "context_window": 8192,
        "role": "Fallback Chat",
    },
    "llama3.2:latest": {
        "name": "llama3.2:latest",
        "context_window": 8192,
        "role": "Fallback Chat",
    },
}


DEFAULT_TASK_MODELS: Dict[TaskType, str] = {
    TaskType.CHAT: "qwen3:8b",
    TaskType.ANALYSIS: "qwen3:8b",
    TaskType.FAST: "gemma:2b",
    TaskType.REASONING: "gemma4:latest",
    TaskType.VISION: "qwen3-vl:latest",
}
