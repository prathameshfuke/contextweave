#!/bin/bash
# ContextWeave Bootstrap Script for Unix/macOS

echo "Initializing ContextWeave environment..."

# Check for uv
if ! command -v uv &> /dev/null
then
    echo "[!] uv is not installed. Installing via pip..."
    pip install uv
fi

# Sync dependencies and install the package
echo "[1/3] Syncing dependencies..."
uv sync --quiet

# Initialize configuration if it doesn't exist
if [ ! -f "$HOME/.contextweave/config.toml" ]; then
    echo "[2/3] First-time setup: Initializing configuration..."
    uv run contextweave init contextweave
else
    echo "[2/3] Configuration found. Skipping init."
fi

chmod +x cw
echo "[3/3] System Ready!"
echo ""
echo "============================================================"
echo "SETUP COMPLETE"
echo "============================================================"
echo "You can now use the './cw' command in this folder."
echo ""
echo "1. Type './cw --help' to get started."
echo "============================================================"
