@echo off
setlocal
cd /d "%~dp0"
title VozFlow - instalacao

echo.
echo ==========================================================
echo    VozFlow - instalando dependencias
echo ==========================================================
echo.

rem Nada de %errorlevel% dentro de parenteses: o cmd expande no parse, nao na hora.
if not exist ".venv\Scripts\python.exe" (
    echo -- criando ambiente virtual .venv --
    py -3 -m venv .venv 2>nul
)
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [ERRO] Nao consegui criar o ambiente virtual .venv
    echo        Verifique se o Python 3.10+ esta instalado.
    pause
    exit /b 1
)

set "PY=.venv\Scripts\python.exe"

echo.
echo -- atualizando pip --
"%PY%" -m pip install --upgrade pip --quiet

echo.
echo -- instalando pacotes (isso pode levar alguns minutos) --
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar as dependencias.
    pause
    exit /b 1
)

nvidia-smi >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo -- GPU NVIDIA detectada: instalando cuBLAS + cuDNN --
    "%PY%" -m pip install -r requirements-gpu.txt
)

echo.
echo -- baixando o modelo de transcricao e checando o microfone --
"%PY%" -m vozflow.diagnostico

echo.
echo ==========================================================
echo    Pronto! Inicie com um duplo clique em VozFlow.vbs
echo    (ou VozFlow-debug.bat se quiser ver os logs)
echo ==========================================================
echo.
pause
