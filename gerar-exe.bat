@echo off
setlocal
cd /d "%~dp0"
title VozFlow - gerando executavel

rem  Uso:  gerar-exe.bat        -> com GPU  (~1,0 GB, transcricao em ~0,3s)
rem        gerar-exe.bat cpu    -> so CPU   (~260 MB, transcricao em segundos)
rem
rem  A receita esta em VozFlow.spec, que documenta o que entra e o que fica de
rem  fora - e por que. Sem esse corte o pacote sairia com 2,3 GB.

if not exist ".venv\Scripts\python.exe" (
    echo Rode o instalar.bat primeiro.
    pause
    exit /b 1
)
set "PY=.venv\Scripts\python.exe"

set "VOZFLOW_CPU="
if /i "%~1"=="cpu" set "VOZFLOW_CPU=1"

echo.
echo ==========================================================
if defined VOZFLOW_CPU (
    echo    Empacotando o VozFlow - versao CPU
    echo    ~260 MB. Transcricao em varios segundos.
) else (
    echo    Empacotando o VozFlow - versao GPU
    echo    ~1,0 GB. Transcricao em ~0,3s numa RTX.
)
echo ==========================================================
echo.

echo -- instalando PyInstaller --
"%PY%" -m pip install --upgrade pyinstaller --quiet

echo.
echo -- empacotando (leva varios minutos) --
"%PY%" -m PyInstaller --noconfirm --clean VozFlow.spec
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao empacotar. Veja a saida acima.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo    Pronto: dist\VozFlow\VozFlow.exe
echo    O modelo de transcricao e baixado no primeiro uso
echo    (~1,6 GB, uma vez so, fica em %%USERPROFILE%%\.cache)
echo.
echo    Para gerar o INSTALADOR: gerar-instalador.bat
echo ==========================================================
echo.
pause
