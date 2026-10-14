@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title CVCounter

pushd "%~dp0"

echo ====================================================================
echo                         CVCounter
echo       Система детекции, трекинга и подсчёта объектов                
echo ====================================================================
echo.

if not exist "venv\Scripts\python.exe" goto :no_venv

:start_server
echo [*] Запуск сервера приложения...
echo.
echo   Веб-интерфейс доступен в браузере:
echo   * http://127.0.0.1:8080
echo.
echo   Для остановки сервера нажмите Ctrl+C
echo ====================================================================
echo.

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
venv\Scripts\python.exe app.py

if errorlevel 1 goto :app_error
popd
goto :eof

:no_venv
echo [!] Виртуальное окружение не обнаружено!
echo Система ещё не установлена или установка не была завершена.
echo.
set "DO_INSTALL="
set /p "DO_INSTALL=Запустить автоматическую установку системы сейчас? [Y/n]: "
if /i "!DO_INSTALL!"=="n" (
    echo.
    echo Запуск отменен. Для установки вручную запустите: install.bat
    popd
    pause
    exit /b 1
)

echo.
echo [*] Запуск автоматической установки...
echo.
call install.bat
if !errorlevel! neq 0 (
    echo.
    echo [ОШИБКА] Установка завершилась с ошибкой.
    popd
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo.
    echo [ОШИБКА] Окружение не найдено после установки.
    popd
    pause
    exit /b 1
)

echo.
echo [*] Установка завершена. Запуск приложения...
echo.
goto :start_server

:app_error
echo.
echo [!] Приложение завершило работу с ошибкой.
popd
pause
exit /b 1