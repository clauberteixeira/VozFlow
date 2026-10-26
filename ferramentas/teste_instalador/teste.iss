; Instalador DESCARTAVEL so para conferir o [Code]/[Run] da atualizacao do
; instalador.iss: mesmo codigo, outra trava, sem desinstalador nem registro.
; Diferencas: trava VozFlowTesteAtualizacao_Mutex, /FALHAR=1 simula erro no
; meio da copia, e o "reabrir a versao antiga" roda escondido.
[Setup]
AppId={{0B8E2D6A-5C1F-4F3B-9A44-7D1E3C2B9F10}
AppName=VozFlowTesteAtualizacao
AppVersion=0.0.1
DefaultDirName={param:DESTINO|C:\nao-usar}
PrivilegesRequired=lowest
Uninstallable=no
CreateUninstallRegKey=no
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=teste-atualizacao
SetupLogging=yes

[Files]
Source: "arquivo.txt"; DestDir: "{app}"
Source: "arquivo2.txt"; DestDir: "{app}"; BeforeInstall: FalharNoMeio

[Run]
Filename: "{cmd}"; Parameters: "/c echo reaberto > ""{app}\reaberto.txt"""; Flags: nowait runhidden; Check: ReabrirDepois

[Code]
var
  Instalou: Boolean;
  AppNaoFechou: Boolean;

function ReabrirDepois(): Boolean;
begin
  Result := ExpandConstant('{param:REABRIR|0}') = '1';
end;

function InitializeSetup(): Boolean;
var
  espera: Integer;
begin
  Result := True;
  if ReabrirDepois() then
  begin
    espera := 0;
    while CheckForMutexes('Global\VozFlowTesteAtualizacao_Mutex') and (espera < 60) do
    begin
      Sleep(500);
      espera := espera + 1;
    end;
    if CheckForMutexes('Global\VozFlowTesteAtualizacao_Mutex') then
    begin
      Log('Atualizacao: o VozFlow nao fechou em 30 s; desistindo.');
      AppNaoFechou := True;
      Result := False;
    end;
  end;
end;

procedure DeinitializeSetup();
var
  voltar: String;
  codigo: Integer;
begin
  voltar := ExpandConstant('{param:VOLTAR|}');
  if ReabrirDepois() and not Instalou and not AppNaoFechou and (voltar <> '') and FileExists(voltar) then
  begin
    Log('Atualizacao nao terminou; reabrindo ' + voltar);
    Exec(voltar, '', '', SW_HIDE, ewNoWait, codigo);
  end;
end;

procedure FalharNoMeio();
begin
  if ExpandConstant('{param:FALHAR|0}') = '2' then
    RaiseException('falha depois do primeiro arquivo');
end;

procedure CurStepChanged(passo: TSetupStep);
begin
  if (passo = ssInstall) and (ExpandConstant('{param:FALHAR|0}') = '1') then
    RaiseException('falha simulada no meio da instalacao');
  if passo = ssPostInstall then
    Instalou := True;
end;
