"""
contextweave — a local-first memory layer for AI coding agents.

SQLite + FTS5 + sqlite-vec + MCP + D3.js viewer.
"""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("contextweave")
except PackageNotFoundError:
    __version__ = "0.2.0"

__all__ = ["__version__"]
