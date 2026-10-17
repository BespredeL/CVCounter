@echo off
chcp 65001
setlocal enabledelayedexpansion
title CVCounter

pushd "%~dp0"

echo ====================================================================
echo                         CVCounter
echo        Object detection, tracking, and counting system
echo ====================================================================
echo.

if not exist "venv\Scripts\python.exe" goto :no_venv

:start_server
echo [*] Starting application server...
echo.

set "APP_URL="
for /f "delims=" %%U in ('venv\Scripts\python.exe -c "import json, os; c=json.load(open('config/config.json', encoding='utf-8')).get('server', {}) if os.path.exists('config/config.json') else {}; p=c.get('port', 8080); h=c.get('host', '127.0.0.1'); t='127.0.0.1' if h in ('0.0.0.0', '', '::') else h; s='' if str(p)=='80' else f':{p}'; print(f'http://{t}{s}')" 2^>nul') do set "APP_URL=%%U"
if not defined APP_URL set "APP_URL=http://127.0.0.1:8080"

echo   Web interface available in browser:
echo   * !APP_URL!
echo.
echo   Press Ctrl+C to stop the server
echo ====================================================================
echo.

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
venv\Scripts\python.exe app.py

if errorlevel 1 goto :app_error
popd
goto :eof

:no_venv
echo [!] Virtual environment not found!
echo The system is not installed yet or installation was not completed.
echo.
set "DO_INSTALL="
set /p "DO_INSTALL=Start automatic system installation now? [Y/n]: "
if /i "!DO_INSTALL!"=="n" (
    echo.
    echo Launch cancelled. To install manually, run: install.bat
    popd
    pause
    exit /b 1
)

echo.
echo [*] Starting automatic installation...
echo.
call install.bat
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Installation failed with errors.
    popd
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo.
    echo [ERROR] Virtual environment not found after installation.
    popd
    pause
    exit /b 1
)

echo.
echo [*] Installation complete. Starting application...
echo.
goto :start_server

:app_error
echo.
echo [!] Application terminated with an error.
popd
pause
exit /b 1