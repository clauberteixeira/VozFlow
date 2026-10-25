@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title VozFlow - gerando instalador

rem  Gera o VozFlow-<versao>-instalador.exe na pasta instalador\
rem  (a versao vem de instalador.iss)
rem  Uso:  gerar-instalador.bat        -> com GPU (grande)
rem        gerar-instalador.bat cpu    -> so CPU (leve)

set "MODO=%~1"

echo.
echo ==========================================================
echo    VozFlow - instalador
echo ==========================================================
echo.

rem ---------- 1. empacotar ----------
if not exist "dist\VozFlow\VozFlow.exe" (
    echo -- executavel ainda nao existe, empacotando primeiro --
    call gerar-exe.bat %MODO% < NUL
)
if not exist "dist\VozFlow\VozFlow.exe" (
    echo.
    echo [ERRO] O empacotamento falhou. Veja o build.log
    pause
    exit /b 1
)

rem ---------- 2. localizar o compilador do Inno Setup ----------
set "ISCC="
for %%D in (
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
) do if exist %%D set "ISCC=%%~D"

if not defined ISCC (
    echo -- Inno Setup nao encontrado, instalando via winget --
    winget install --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
    for %%D in (
        "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
        "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
        "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    ) do if exist %%D set "ISCC=%%~D"
)

if not defined ISCC (
    echo.
    echo [ERRO] Nao encontrei o ISCC.exe do Inno Setup.
    echo        Instale de https://jrsoftware.org/isdl.php e rode de novo.
    pause
    exit /b 1
)

echo -- compilador: !ISCC!
echo.
echo -- montando o instalador --
"!ISCC!" instalador.iss
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao montar o instalador.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo    Pronto: instalador\VozFlow-(versao)-instalador.exe
echo.
echo    Instala sem pedir administrador, em
echo    %%LOCALAPPDATA%%\Programs\VozFlow
echo    e aparece em Aplicativos Instalados para desinstalar.
echo ==========================================================
echo.
pause
