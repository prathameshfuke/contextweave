#!/bin/bash
set -e

# ANSI colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Installing ContextWeave...${NC}\n"

# 1. Check Python 3.11+
echo -n "Checking Python version... "
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if awk 'BEGIN {exit !('$PY_VER' >= 3.11)}'; then
        echo -e "${GREEN}Python $PY_VER found.${NC}"
    else
        echo -e "${RED}Python $PY_VER found, but 3.11+ is required.${NC}"
        exit 1
    fi
else
    echo -e "${RED}Python 3 not found. Please install Python 3.11+.${NC}"
    exit 1
fi

# 2. Install uv if not present
echo -n "Checking for uv... "
if command -v uv &>/dev/null; then
    echo -e "${GREEN}uv found.${NC}"
else
    echo -e "${YELLOW}uv not found. Installing...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 3. uv pip install -e .
echo "Installing ContextWeave package..."
uv pip install --system -e .
echo -e "${GREEN}ContextWeave installed successfully.${NC}"

# 4. Check Ollama
echo -n "Checking for Ollama... "
if command -v ollama &>/dev/null; then
    echo -e "${GREEN}Ollama found.${NC}"
else
    echo -e "${RED}Ollama not found.${NC}"
    echo "Please install Ollama from https://ollama.com and run 'OLLAMA_ORIGINS=* ollama serve'."
    exit 1
fi

# 5. Check if mistral is pulled
echo -n "Checking if Ollama mistral model is pulled... "
if ollama list | grep -q "mistral"; then
    echo -e "${GREEN}mistral model found.${NC}"
else
    echo -e "${YELLOW}mistral model not found. Pulling...${NC}"
    ollama pull mistral
fi

# 6. Create ~/.contextweave/
echo "Setting up config directory..."
mkdir -p ~/.contextweave

# 7. Copy config.example.toml to config.toml
if [ ! -f ~/.contextweave/config.toml ]; then
    if [ -f config.example.toml ]; then
        cp config.example.toml ~/.contextweave/config.toml
        echo -e "${GREEN}Created default config.toml.${NC}"
    else
        echo -e "${YELLOW}config.example.toml not found, creating an empty config.toml...${NC}"
        echo 'vault_path = ""' > ~/.contextweave/config.toml
    fi
else
    echo -e "${GREEN}config.toml already exists.${NC}"
fi

# 8. Ask user for vault path
echo -e "\n${YELLOW}Where is your Obsidian Vault located?${NC} (Provide absolute path)"
read -p "> " VAULT_PATH
if [ -n "$VAULT_PATH" ]; then
    # Expand ~ if used
    VAULT_PATH="${VAULT_PATH/#\~/$HOME}"
    # Replace the vault_path line in config.toml
    sed -i.bak "s|^vault_path.*|vault_path = \"$VAULT_PATH\"|" ~/.contextweave/config.toml
    echo -e "${GREEN}Vault path saved to config.toml.${NC}"
fi

# 9. Run contextweave doctor
echo -e "\nRunning ${YELLOW}contextweave doctor${NC}..."
contextweave doctor

# 10. Print next steps
echo -e "\n========================================================"
echo -e "${GREEN}Setup complete!${NC}"
echo -e "Now install the Obsidian Local REST API plugin:"
echo -e "${YELLOW}https://github.com/coddingtonbear/obsidian-local-rest-api${NC}"
echo -e "Make sure it is running on port 27123."
echo -e "Then run: ${YELLOW}contextweave doctor${NC} again to confirm everything is green."
echo -e "========================================================"
