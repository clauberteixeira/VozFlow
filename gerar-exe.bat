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

rem  Build reprodutivel: as dependencias do executavel saem das versoes e
rem  hashes de requirements-lock.txt (nao "a versao do dia"), e o PyInstaller
rem  fica numa versao fixa. Para atualizar, veja docs\EMPACOTAMENTO.md.
echo -- sincronizando dependencias com requirements-lock.txt --
"%PY%" -m pip install --require-hashes -r requirements-lock.txt --quiet
if errorlevel 1 (
    echo.
    echo [ERRO] As dependencias nao batem com requirements-lock.txt.
    pause
    exit /b 1
)

echo -- instalando PyInstaller --
"%PY%" -m pip install pyinstaller==6.22.2 pyinstaller-hooks-contrib==2026.7 --quiet
if errorlevel 1 (
    echo.
    echo [ERRO] Nao consegui instalar o PyInstaller 6.22.2.
    pause
    exit /b 1
)

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
echo    (1,6 GB com GPU, ~145 MB sem; uma vez so, fica em %%USERPROFILE%%\.cache)
echo.
echo    Para gerar o INSTALADOR: gerar-instalador.bat
echo ==========================================================
echo.
pause
