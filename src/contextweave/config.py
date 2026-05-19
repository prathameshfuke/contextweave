import os
from pathlib import Path
import toml
from typing import Dict, Any
import click
from rich.console import Console

console = Console()

CONFIG_DIR = Path.home() / ".contextweave"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "vault_path": "",
    "default_project": "my-project",
    "ollama_model": "mistral",
    "ollama_url": "http://localhost:11434",
    "obsidian_api_key": "",
    "obsidian_port": 27123
}

def load_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = DEFAULT_CONFIG.copy()
        
        console.print("[yellow]Configuration file not found. Initializing...[/yellow]")
        vault_path = click.prompt("Enter the path to your Obsidian vault")
        config["vault_path"] = str(Path(vault_path).expanduser().resolve())
        
        save_config(config)
        return config
    
    try:
        with open(CONFIG_FILE, "r") as f:
            config = toml.load(f)
            # Ensure all default keys exist
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return DEFAULT_CONFIG

def save_config(config: Dict[str, Any]) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            toml.dump(config, f)
        console.print(f"[green]Configuration saved to {CONFIG_FILE}[/green]")
    except Exception as e:
        console.print(f"[red]Error saving config: {e}[/red]")
