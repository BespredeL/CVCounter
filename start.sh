#!/usr/bin/env bash
# ====================================================================
# CVCounter - Startup Script for Linux / macOS
# ====================================================================

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

if [ ! -f "venv/bin/python" ]; then
    echo "[ERROR] Virtual environment not found!"
    echo "Please run the installation first: ./install.sh"
    exit 1
fi

APP_URL=$(venv/bin/python -c "import json, os; c=json.load(open('config/config.json', encoding='utf-8')).get('server', {}) if os.path.exists('config/config.json') else {}; p=c.get('port', 8080); h=c.get('host', '127.0.0.1'); t='127.0.0.1' if h in ('0.0.0.0', '', '::') else h; s='' if str(p)=='80' else f':{p}'; print(f'http://{t}{s}')" 2>/dev/null || echo "http://127.0.0.1:8080")

echo "===================================================================="
echo "                 Starting CVCounter...                              "
echo "  Web interface: ${APP_URL}"
echo "  Stop server:   Ctrl+C                                               "
echo "===================================================================="
echo ""

venv/bin/python app.py
