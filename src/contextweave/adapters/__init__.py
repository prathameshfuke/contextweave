from .base import BaseAdapter
from .claude_code import ClaudeCodeAdapter
from .gemini import GeminiAdapter
from .copilot import CopilotAdapter
from .generic import GenericAdapter

ADAPTERS = {
    "claude": ClaudeCodeAdapter(),
    "gemini": GeminiAdapter(),
    "copilot": CopilotAdapter(),
    "generic": GenericAdapter(),
}

def get_adapter(name: str) -> BaseAdapter:
    if name not in ADAPTERS:
        raise ValueError(f"Unknown adapter '{name}'. Available: {list(ADAPTERS.keys())}")
    return ADAPTERS[name]
