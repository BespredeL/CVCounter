#!/usr/bin/env bash
# ====================================================================
# CVCounterWEB - Универсальный установщик для Linux / macOS
# ====================================================================

set -e

echo "===================================================================="
echo "              CVCounterWEB - Установка системы (Linux / macOS)      "
echo "===================================================================="
echo ""

# 1. Поиск Python 3.10 .. 3.12
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

if [ -z "$PYTHON_BIN" ]; then
    echo "[ОШИБКА] Python не найден! Установите python3 (рекомендуется python3.11-venv)."
    exit 1
fi

echo "[1/4] Используется Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# 2. Создание venv
if [ ! -f "venv/bin/python" ]; then
    echo "[2/4] Создание виртуального окружения venv..."
    $PYTHON_BIN -m venv venv
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
