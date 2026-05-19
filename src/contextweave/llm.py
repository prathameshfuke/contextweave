import requests
from typing import List, Dict, Any
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
            return response.json().get("response", "")
        except requests.exceptions.RequestException:
            console.print("[red]Ollama is not running. Start it with: ollama serve[/red]")
            return ""

    def summarise(self, text: str, instruction: str) -> str:
        system = "You are a context summariser for a software project. Be concise, structured, and technical. Output markdown only."
        prompt = f"{instruction}\n\n{text}"
        return self.generate(prompt, system)

    def compress_chat(self, raw_turns: List[Dict[str, str]]) -> str:
        transcript = ""
        for turn in raw_turns:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            transcript += f"{role.upper()}: {content}\n\n"

        instruction = """Convert this AI chat into a structured handoff document another AI can read to continue the work.
Include:
- Project/task being worked on (2 sentences max)
- Key decisions made (bullet list with reasoning)
- Current state: what is done, what is in progress
- Critical constraints or patterns to follow
- Exact next step (be specific, mention file names)
- Open questions
Output as markdown with these exact headers. Be ruthlessly concise."""
        
        return self.summarise(transcript, instruction)
