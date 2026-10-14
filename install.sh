#!/usr/bin/env bash
# ====================================================================
# CVCounter - Универсальный установщик для Linux / macOS
# ====================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "===================================================================="
echo "              CVCounter - Установка системы (Linux / macOS)      "
echo "===================================================================="
echo ""

# Функция поиска Python
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

# 1. Поиск Python 3.10 .. 3.12
find_python

if [ -z "$PYTHON_BIN" ]; then
    echo "[!] Совместимый Python (3.10 - 3.12) не обнаружен в системе."
    echo "[*] Попытка автоматической установки через пакетный менеджер..."

    if command -v apt-get >/dev/null 2>&1; then
        echo "[*] Обнаружен apt (Debian/Ubuntu). Установка Python 3.11 и python3-venv..."
        sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv python3-pip || sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v dnf >/dev/null 2>&1; then
        echo "[*] Обнаружен dnf (Fedora/RHEL). Установка Python 3.11..."
        sudo dnf install -y python3.11 python3.11-pip || sudo dnf install -y python3 python3-pip
    elif command -v pacman >/dev/null 2>&1; then
        echo "[*] Обнаружен pacman (Arch Linux). Установка Python..."
        sudo pacman -Sy --noconfirm python python-pip
    elif command -v brew >/dev/null 2>&1; then
        echo "[*] Обнаружен Homebrew (macOS). Установка Python 3.11..."
        brew install python@3.11
    fi

    find_python
fi

if [ -z "$PYTHON_BIN" ]; then
    echo ""
    echo "[ОШИБКА] Не удалось найти или установить Python!"
    echo "Пожалуйста, установите python3 и модуль venv вручную:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install -y python3.11 python3.11-venv"
    echo "  Fedora/RHEL:   sudo dnf install -y python3.11"
    echo "  macOS:         brew install python@3.11"
    echo ""
    exit 1
fi

echo "[1/4] Используется Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# 2. Создание venv
if [ ! -f "venv/bin/python" ]; then
    if [ -d "venv" ]; then
        echo "[*] Очистка повреждённого каталога venv..."
        rm -rf "venv"
    fi
    echo "[2/4] Создание виртуального окружения venv..."
    if ! $PYTHON_BIN -m venv venv 2>/dev/null; then
        echo "[!] Ошибка создания venv. Возможно, не установлен пакет python3-venv."
        if command -v apt-get >/dev/null 2>&1; then
            echo "[*] Установка пакета python3-venv..."
            sudo apt-get install -y python3-venv python3.11-venv || true
            $PYTHON_BIN -m venv venv
        else
            echo "[ОШИБКА] Не удалось создать виртуальное окружение. Установите python3-venv."
            exit 1
        fi
    fi
else
    echo "[2/4] Виртуальное окружение venv уже существует."
fi

# 3. Подготовка pip
echo "[3/4] Обновление базовых инструментов pip..."
venv/bin/python -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true

# 4. Запуск установщика оборудования
echo "[4/4] Запуск автоопределения оборудования и установки зависимостей..."
venv/bin/python install.py "$@"

echo ""
echo "===================================================================="
echo "  Установка завершена! Запуск: ./start.sh или venv/bin/python app.py"
echo "===================================================================="
