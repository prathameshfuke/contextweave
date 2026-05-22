"""
cli.py — Root forwarder to src/contextweave/_cli_entry.py.
"""
import sys
from pathlib import Path

# Add src to sys.path
_src = Path(__file__).parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from contextweave._cli_entry import main

if __name__ == "__main__":
    main()
