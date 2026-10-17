#!/usr/bin/env bash
# ====================================================================
# CVCounter - Universal Installer for Linux / macOS
# ====================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "===================================================================="
echo "              CVCounter - Setup / Installer (Linux / macOS)         "
echo "===================================================================="
echo ""

# Python detection function
find_python() {
    PYTHON_BIN=""
    for cmd in python3.11 python3.12 python3.10 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            PY_VER=$("$cmd" -c "import sys; print(sys.version_info[0], sys.version_info[1])" 2>/dev/null || true)
            if [ "$PY_VER" = "3 11" ] || [ "$PY_VER" = "3 12" ] || [ "$PY_VER" = "3 10" ]; then
                PYTHON_BIN="$cmd"
                break
            elif [ -z "$PYTHON_BIN" ]; then
                PYTHON_BIN="$cmd"
            fi
        fi
    done
}

# 1. Search for Python 3.10 .. 3.12
find_python

if [ -z "$PYTHON_BIN" ]; then
    echo "[!] Compatible Python (3.10 - 3.12) was not found on the system."
    echo "[*] Attempting automatic installation via package manager..."

    if command -v apt-get >/dev/null 2>&1; then
        echo "[*] Detected apt (Debian/Ubuntu). Installing Python 3.11 and python3-venv..."
        sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv python3-pip || sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v dnf >/dev/null 2>&1; then
        echo "[*] Detected dnf (Fedora/RHEL). Installing Python 3.11..."
        sudo dnf install -y python3.11 python3.11-pip || sudo dnf install -y python3 python3-pip
    elif command -v pacman >/dev/null 2>&1; then
        echo "[*] Detected pacman (Arch Linux). Installing Python..."
        sudo pacman -Sy --noconfirm python python-pip
    elif command -v brew >/dev/null 2>&1; then
        echo "[*] Detected Homebrew (macOS). Installing Python 3.11..."
        brew install python@3.11
    fi

    find_python
fi

if [ -z "$PYTHON_BIN" ]; then
    echo ""
    echo "[ERROR] Failed to find or install Python!"
    echo "Please install python3 and venv module manually:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install -y python3.11 python3.11-venv"
    echo "  Fedora/RHEL:   sudo dnf install -y python3.11"
    echo "  macOS:         brew install python@3.11"
    echo ""
    exit 1
fi

echo "[1/4] Using Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# 2. Virtual environment creation
if [ ! -f "venv/bin/python" ]; then
    if [ -d "venv" ]; then
        echo "[*] Cleaning incomplete venv directory..."
        rm -rf "venv"
    fi
    echo "[2/4] Creating virtual environment 'venv'..."
    if ! $PYTHON_BIN -m venv venv 2>/dev/null; then
        echo "[!] Error creating venv. The python3-venv package might be missing."
        if command -v apt-get >/dev/null 2>&1; then
            echo "[*] Installing python3-venv package..."
            sudo apt-get install -y python3-venv python3.11-venv || true
            $PYTHON_BIN -m venv venv
        else
            echo "[ERROR] Failed to create virtual environment. Please install python3-venv."
            exit 1
        fi
    fi
else
    echo "[2/4] Virtual environment 'venv' already exists."
fi

# 3. Prepare pip
echo "[3/4] Updating base pip tools..."
venv/bin/python -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true

# 4. Launch hardware auto-detection and dependency installation
echo "[4/4] Launching hardware auto-detection and dependencies installer..."
venv/bin/python install.py "$@"

echo ""
echo "===================================================================="
echo "  INSTALLATION COMPLETED! Run: ./start.sh or venv/bin/python app.py "
echo "===================================================================="
