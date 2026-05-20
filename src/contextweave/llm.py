import requests
from typing import List, Dict
from rich.console import Console
from .config import load_config

console = Console()

class LLM:
    def __init__(self):
        config = load_config()
        self.url = config.get("ollama_url", "http://localhost:11434")
        self.model = config.get("ollama_model", "mistral")

    def generate(self, prompt: str, system: str = "") -> str:
        try:
            url = f"{self.url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": False
            }
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.exceptions.RequestException:
            console.print("[red]Ollama is not running. Start it with: ollama serve[/red]")
            return ""

    def summarise(self, text: str, instruction: str) -> str:
        system = "You are a context summariser for a software project. Be concise, structured, and technical. Output markdown only."
        prompt = f"{instruction}\n\n{text}"
        return self.generate(prompt, system)

    def compress_chat(self, raw_turns: List[Dict[str, str]]) -> str:
        transcript = []
        for index, turn in enumerate(raw_turns, 1):
            role = turn.get("role", "unknown").strip().title()
            content = turn.get("content", "").strip()
            if not content:
                continue
            transcript.append(f"### Turn {index} — {role}\n{content}")

        instruction = """Convert this AI chat into a structured handoff another AI can continue from.
Use these exact markdown headers:
## Project / Task
## Key Decisions
## Current State
## Critical Constraints
## Exact Next Step
## Open Questions

Rules:
- Be concise and specific.
- Mention file names and concrete next actions when present.
- Use bullet points under sections where helpful.
- Do not add any prose outside the required headers."""

        return self.summarise("\n\n".join(transcript), instruction)

def summarise(text: str, instruction: str) -> str:
    return LLM().summarise(text, instruction)
