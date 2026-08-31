@echo off
cd /d "%~dp0"
title VozFlow (modo debug)
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente nao encontrado. Rode o instalar.bat primeiro.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
echo.
echo --- VozFlow encerrado ---
pause
