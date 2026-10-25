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

rem ---------- 3. checksum para quem baixa conferir ----------
rem  O instalador nao e assinado (ver docs\EMPACOTAMENTO.md). O SHA-256 vai
rem  num .sha256 ao lado dele e no texto da Release: quem baixa confere que o
rem  arquivo e exatamente o que saiu daqui.
set "INST="
for /f "delims=" %%F in ('dir /b /o-d "instalador\VozFlow-*-instalador.exe"') do (
    if not defined INST set "INST=instalador\%%F"
)
if not defined INST goto :sem_hash
rem  Apaga o anterior: se o PowerShell falhar, um .sha256 velho de outra build
rem  da mesma versao iria para a Release com o hash errado.
if exist "!INST!.sha256" del "!INST!.sha256"
rem  Fora de bloco ( ) e sem aspas internas: o cmd quebra o parser com \" la dentro.
rem  Gravado com LF pelo proprio PowerShell: com CRLF o "sha256sum -c" recusa.
powershell -NoProfile -Command "$f='!INST!'; $l=(Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash.ToLower() + '  ' + (Split-Path -Leaf $f) + [char]10; [IO.File]::WriteAllText((Join-Path $PWD ($f + '.sha256')), $l)"
if errorlevel 1 (
    echo [ERRO] Nao consegui calcular o SHA-256 do instalador.
    pause
    exit /b 1
)
echo -- SHA-256 gravado em !INST!.sha256
type "!INST!.sha256"
:sem_hash

echo.
echo ==========================================================
if defined INST (
    echo    Pronto: !INST!
    echo    Publique tambem o !INST!.sha256 na Release.
) else (
    echo    [AVISO] nao achei o instalador na pasta instalador
)
echo.
echo    Instala sem pedir administrador, em
echo    %%LOCALAPPDATA%%\Programs\VozFlow
echo    e aparece em Aplicativos Instalados para desinstalar.
echo ==========================================================
echo.
pause
