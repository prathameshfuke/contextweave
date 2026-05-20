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

class ConfigError(RuntimeError):
    """Raised when ContextWeave configuration cannot be used."""

def _normalise_vault_path(vault_path: Any) -> str:
    if not isinstance(vault_path, str) or not vault_path.strip():
        raise ConfigError(
            f"Vault path is not configured. Set vault_path in {CONFIG_FILE} "
            "or delete the file to run first-time setup again."
        )

    path = Path(vault_path).expanduser().resolve()
    if not path.exists():
        raise ConfigError(f"Configured vault path does not exist: {path}")
    if not path.is_dir():
        raise ConfigError(f"Configured vault path is not a directory: {path}")
    return str(path)

def _prompt_for_config() -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()

    console.print("[yellow]Configuration file not found. Initializing...[/yellow]")
    vault_path = click.prompt(
        "Enter the path to your Obsidian vault",
        type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
    )
    config["vault_path"] = _normalise_vault_path(vault_path)

    save_config(config)
    return config

def load_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        return _prompt_for_config()
    
    try:
        with open(CONFIG_FILE, "r") as f:
            config = toml.load(f)
            # Ensure all default keys exist
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            config["vault_path"] = _normalise_vault_path(config.get("vault_path"))
            return config
    except ConfigError:
        raise
    except toml.TomlDecodeError as e:
        raise ConfigError(f"Invalid TOML in {CONFIG_FILE}: {e}") from e
    except OSError as e:
        raise ConfigError(f"Could not read config file {CONFIG_FILE}: {e}") from e

def save_config(config: Dict[str, Any]) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            toml.dump(config, f)
        console.print(f"[green]Configuration saved to {CONFIG_FILE}[/green]")
    except Exception as e:
        raise ConfigError(f"Could not save config file {CONFIG_FILE}: {e}") from e
