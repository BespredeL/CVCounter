@echo off
title CVCounterWEB
chcp 65001 >nul

echo ====================================================================
echo                         CVCounterWEB                                
echo       Система детекции, трекинга и подсчёта объектов                
echo ====================================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ОШИБКА] Виртуальное окружение не обнаружено!
    echo.
    echo Пожалуйста, сначала выполните установку, запустив install.bat
    echo.
    pause
    exit /b 1
)

echo [*] Запуск сервера приложения...
echo.
echo   Веб-интерфейс будет доступен по адресу:
echo   -> http://127.0.0.1:5000  (или порт, указанный в config.json)
echo.
echo   Для остановки сервера нажмите Ctrl+C в этом окне.
echo ====================================================================
echo.

venv\Scripts\python.exe app.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Приложение завершило работу с ошибкой (код %errorlevel%).
    pause
)