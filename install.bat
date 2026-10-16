@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title CVCounter - Installer

pushd "%~dp0"

echo ====================================================================
echo                   CVCounter - Setup / Installer
echo ====================================================================
echo.
echo Automatic environment setup and hardware optimization (GPU/CPU).
echo.

echo [1/5] Checking Python 3.10 - 3.12...

set "PYTHON_EXE="

call :detect_python

if not defined PYTHON_EXE (
    echo.
    echo [*] Compatible Python [3.10 - 3.12] was not found.
    echo [*] Downloading and installing Python 3.11 [64-bit] automatically...
    echo.
    call :install_python_auto
    call :detect_python
)

if not defined PYTHON_EXE (
    echo.
    echo ====================================================================
    echo [ERROR] Failed to install Python automatically!
    echo.
    echo Please install Python 3.11 manually:
    echo 1. Download installer: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo 2. Run installer and MAKE SURE to check:
    echo    [X] Add python.exe to PATH
    echo 3. Run install.bat again.
    echo ====================================================================
    echo.
    popd
    pause
    exit /b 1
)

echo   * Using Python: !PYTHON_EXE!
echo.

echo [2/5] Checking Microsoft Visual C++ 2015-2022 Redistributable [x64]...

set "VC_NEED_INSTALL=0"
if not exist "%SystemRoot%\System32\vcruntime140_1.dll" set "VC_NEED_INSTALL=1"
if not exist "%SystemRoot%\System32\msvcp140.dll" set "VC_NEED_INSTALL=1"

if "!VC_NEED_INSTALL!"=="1" (
    echo [!] Missing Microsoft Visual C++ Redistributable [x64].
    echo [*] Required for PyTorch [c10.dll] and ONNX Runtime.
    echo [*] Downloading and installing Visual C++ automatically...
    call :install_vcredist_auto
) else (
    echo   * Microsoft Visual C++ Redistributable found.
)
echo.

echo [3/5] Checking virtual environment [venv]...

if not exist "venv\Scripts\python.exe" (
    if exist "venv" (
        echo [*] Cleaning incomplete venv directory...
        rmdir /s /q "venv" >nul 2>&1
    )
    echo [*] Creating isolated virtual environment 'venv'...
    "!PYTHON_EXE!" -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment!
        echo Please remove venv folder and run install.bat as Administrator.
        popd
        pause
        exit /b 1
    )
    echo   * Virtual environment created successfully.
) else (
    echo   * Virtual environment already exists.
)
echo.

echo [4/5] Preparing package manager [pip]...
venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel >nul 2>&1

echo [5/5] Launching hardware auto-detection and dependencies installer...
echo.

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
venv\Scripts\python.exe install.py %*

set "EXIT_CODE=%errorlevel%"
echo.
if %EXIT_CODE% equ 0 goto :install_success
goto :install_failed

:install_success
echo ====================================================================
echo   INSTALLATION COMPLETED! / УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!
echo ====================================================================
echo.
echo   To launch the application, run: start.bat
echo   Web interface will be available at: http://127.0.0.1:80  [or http://localhost]
echo.
popd
pause
exit /b 0

:install_failed
echo ====================================================================
echo   Installation finished with errors. See details above.
echo ====================================================================
echo.
popd
pause
exit /b %EXIT_CODE%


:: ====================================================================
:: ПОДПРОГРАММЫ ПОИСКА И УСТАНОВКИ PYTHON
:: ====================================================================

:detect_python
set "PYTHON_EXE="

:: 1. Проверка через системный лаунчер py (3.11, 3.12, 3.10)
for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do (
    set "PYTHON_EXE=%%I"
    goto :detect_done
)
for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do (
    set "PYTHON_EXE=%%I"
    goto :detect_done
)
for /f "delims=" %%I in ('py -3.10 -c "import sys; print(sys.executable)" 2^>nul') do (
    set "PYTHON_EXE=%%I"
    goto :detect_done
)

:: 2. Проверка типичных путей установки Python на Windows
for %%P in (
    "%LocalAppData%\Programs\Python\Python311\python.exe"
    "%ProgramFiles%\Python311\python.exe"
    "C:\Program Files\Python311\python.exe"
    "%LocalAppData%\Programs\Python\Python312\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "C:\Program Files\Python312\python.exe"
    "%LocalAppData%\Programs\Python\Python310\python.exe"
    "%ProgramFiles%\Python310\python.exe"
    "C:\Program Files\Python310\python.exe"
    "%ProgramFiles(x86)%\Python311\python.exe"
) do (
    if exist %%P (
        %%P -c "import sys; exit(0)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=%%~P"
            goto :detect_done
        )
    )
)

:: 3. Проверка команды python в PATH (исключая заглушку Microsoft Store и неподдерживаемые версии)
for /f "delims=" %%I in ('python -c "import sys; print(sys.executable) if sys.version_info.major == 3 and sys.version_info.minor in (10, 11, 12) else sys.exit(1)" 2^>nul') do (
    set "PYTHON_EXE=%%I"
    goto :detect_done
)

:detect_done
if defined PYTHON_EXE (
    for %%D in ("!PYTHON_EXE!") do (
        set "PY_DIR=%%~dpD"
        set "PY_DIR=!PY_DIR:~0,-1!"
        set "PATH=!PY_DIR!;!PY_DIR!\Scripts;!PATH!"
    )
)
exit /b 0


:install_python_auto
set "PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
set "PY_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"

if exist "!PY_INSTALLER!" del /f /q "!PY_INSTALLER!" >nul 2>&1

echo [*] Загрузка официального установщика Python 3.11.9...

set "DOWNLOAD_OK=0"

:: Метод 1: curl.exe
where curl.exe >nul 2>&1
if !errorlevel! equ 0 (
    echo   -> Скачивание через curl...
    curl.exe -fSLo "!PY_INSTALLER!" "!PY_URL!"
    if exist "!PY_INSTALLER!" (
        for %%A in ("!PY_INSTALLER!") do (
            if %%~zA gtr 1000000 set "DOWNLOAD_OK=1"
        )
    )
)

:: Метод 2: PowerShell (если curl недоступен или не загрузил файл)
if "!DOWNLOAD_OK!"=="0" (
    echo   -> Скачивание через PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; try { (New-Object System.Net.WebClient).DownloadFile('!PY_URL!', '!PY_INSTALLER!'); exit 0 } catch { exit 1 }"
    if exist "!PY_INSTALLER!" (
        for %%A in ("!PY_INSTALLER!") do (
            if %%~zA gtr 1000000 set "DOWNLOAD_OK=1"
        )
    )
)

:: Если установщик скачан, выполняем тихую установку
if "!DOWNLOAD_OK!"=="1" (
    echo [*] Установщик загружен. Выполняется автоматическая тихая установка...
    echo [*] Пожалуйста, подождите [обычно занимает около 20-40 секунд]...
    start /wait "" "!PY_INSTALLER!" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1 Include_launcher=1 SimpleInstall=1
    del /f /q "!PY_INSTALLER!" >nul 2>&1
    call :detect_python
    if defined PYTHON_EXE exit /b 0
)

:: Метод 3: winget (запасной вариант)
where winget.exe >nul 2>&1
if !errorlevel! equ 0 (
    echo [*] Попытка установки через Windows Package Manager [winget]...
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements --scope user
    call :detect_python
    if defined PYTHON_EXE exit /b 0
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    call :detect_python
    if defined PYTHON_EXE exit /b 0
)

exit /b 0


:install_vcredist_auto
set "VC_URL=https://aka.ms/vs/17/release/vc_redist.x64.exe"
set "VC_INSTALLER=%TEMP%\vc_redist.x64.exe"

if exist "!VC_INSTALLER!" del /f /q "!VC_INSTALLER!" >nul 2>&1

echo [*] Загрузка vc_redist.x64.exe с серверов Microsoft...

set "VC_DOWNLOAD_OK=0"

where curl.exe >nul 2>&1
if !errorlevel! equ 0 (
    echo   -> Скачивание через curl...
    curl.exe -fSLo "!VC_INSTALLER!" "!VC_URL!"
    if exist "!VC_INSTALLER!" (
        for %%A in ("!VC_INSTALLER!") do (
            if %%~zA gtr 5000000 set "VC_DOWNLOAD_OK=1"
        )
    )
)

if "!VC_DOWNLOAD_OK!"=="0" (
    echo   -> Скачивание через PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; try { (New-Object System.Net.WebClient).DownloadFile('!VC_URL!', '!VC_INSTALLER!'); exit 0 } catch { exit 1 }"
    if exist "!VC_INSTALLER!" (
        for %%A in ("!VC_INSTALLER!") do (
            if %%~zA gtr 5000000 set "VC_DOWNLOAD_OK=1"
        )
    )
)

if "!VC_DOWNLOAD_OK!"=="1" (
    echo [*] Установка Visual C++ 2015-2022 Redistributable...
    echo [*] Пожалуйста, подождите [обычно занимает 5-15 секунд]...
    start /wait "" "!VC_INSTALLER!" /install /quiet /norestart
    if not exist "%SystemRoot%\System32\vcruntime140_1.dll" (
        echo [*] Запуск установщика с запросом подтверждения UAC...
        start /wait "" "!VC_INSTALLER!" /install /norestart
    )
    del /f /q "!VC_INSTALLER!" >nul 2>&1
    if exist "%SystemRoot%\System32\vcruntime140_1.dll" (
        echo   * Visual C++ Redistributable успешно установлен.
        exit /b 0
    )
)

where winget.exe >nul 2>&1
if !errorlevel! equ 0 (
    echo [*] Попытка установки через Windows Package Manager [winget]...
    winget install Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements
    if exist "%SystemRoot%\System32\vcruntime140_1.dll" (
        echo   * Visual C++ Redistributable успешно установлен.
        exit /b 0
    )
)

echo [!] Не удалось автоматически установить Visual C++ Redistributable.
echo Скачайте и установите его вручную: https://aka.ms/vs/17/release/vc_redist.x64.exe
exit /b 0
