@echo off
chcp 65001 >nul
title CVCounterWEB

echo ====================================================================
echo                         CVCounterWEB                                
echo       Система детекции, трекинга и подсчёта объектов                
echo ====================================================================
echo.

if not exist "venv\Scripts\python.exe" goto :no_venv

echo [*] Запуск сервера приложения...
echo.
echo   Веб-интерфейс доступен в браузере:
echo   * http://127.0.0.1:5000
echo.
echo   Для остановки сервера нажмите Ctrl+C
echo ====================================================================
echo.

venv\Scripts\python.exe app.py

if errorlevel 1 goto :app_error
goto :eof

:no_venv
echo [ОШИБКА] Виртуальное окружение не обнаружено!
echo.
echo Пожалуйста, сначала выполните установку: запустите install.bat
echo.
pause
exit /b 1

:app_error
echo.
echo [!] Приложение завершило работу с ошибкой.
pause
exit /b 1