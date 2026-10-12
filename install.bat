@echo off
setlocal enabledelayedexpansion
title CVCounterWEB - Автоматическая установка
chcp 65001 >nul

echo ====================================================================
echo                   CVCounterWEB - Установка системы
echo ====================================================================
echo.
echo Данный скрипт автоматически настроит окружение, определит вашу
echo видеокарту (NVIDIA, AMD или Intel) и установит все необходимые
echo компоненты для максимальной производительности нейросетей.
echo.

echo [1/4] Поиск совместимой версии Python...

set "PYTHON_EXE="

py -3.11 -c "import sys; exit(0)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3.11"
    goto :python_found
)

py -3.12 -c "import sys; exit(0)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3.12"
    goto :python_found
)

py -3.10 -c "import sys; exit(0)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3.10"
    goto :python_found
)

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    goto :python_found
)
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
    goto :python_found
)
if exist "%LocalAppData%\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python310\python.exe"
    goto :python_found
)
if exist "C:\Program Files\Python311\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
    goto :python_found
)
if exist "C:\Program Files\Python312\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
    goto :python_found
)

python -c "import sys; exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=python"
    goto :python_found
)

python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=python"
    echo [!] Обнаружен системный Python, но рекомендуется версия 3.11 для лучшей совместимости с CUDA.
    goto :python_found
)

echo [!] Python не обнаружен в системе!
echo Попытка автоматической установки Python 3.11...

winget --version >nul 2>&1
if !errorlevel! equ 0 (
    echo [*] Установка Python 3.11 через Windows Package Manager (winget)...
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
        goto :python_found
    )
)

echo [ОШИБКА] Не удалось найти или автоматически установить Python!
echo Пожалуйста, установите Python 3.11 с официального сайта:
echo https://www.python.org/downloads/release/python-3119/
echo ВАЖНО: При установке обязательно отметьте галочку:
echo Add python.exe to PATH
echo.
pause
exit /b 1

:python_found
echo   * Найден Python: !PYTHON_EXE!
echo.

echo [2/4] Проверка виртуального окружения (venv)...

if not exist "venv\Scripts\python.exe" (
    echo [*] Создание изолированного виртуального окружения 'venv'...
    !PYTHON_EXE! -m venv venv
    if !errorlevel! neq 0 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение!
        pause
        exit /b 1
    )
    echo   * Виртуальное окружение успешно создано.
) else (
    echo   * Виртуальное окружение уже существует.
)
echo.

echo [3/4] Проверка и подготовка менеджера пакетов...
venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel >nul 2>&1

echo [4/4] Запуск автоопределения оборудования и установки библиотек...
echo.

venv\Scripts\python.exe install.py

set "EXIT_CODE=%errorlevel%"
echo.
if %EXIT_CODE% equ 0 goto :install_success
goto :install_failed

:install_success
echo ====================================================================
echo   УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!
echo ====================================================================
echo.
echo   Для запуска системы откройте файл: start.bat
echo   Веб-интерфейс будет доступен по адресу: http://127.0.0.1:5000
echo.
pause
exit /b 0

:install_failed
echo ====================================================================
echo   В процессе установки возникли ошибки.
echo   Ознакомьтесь с сообщениями выше.
echo ====================================================================
echo.
pause
exit /b %EXIT_CODE%
