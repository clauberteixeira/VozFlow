; Instalador do VozFlow - compilado por gerar-instalador.bat
;
; Instala por usuario (sem UAC) em %LOCALAPPDATA%\Programs\VozFlow.
; A opcao "iniciar com o Windows" grava exatamente o mesmo VozFlow.vbs que a
; tela de configuracoes do app cria e remove - assim as duas nunca divergem.

#define Nome      "VozFlow"
#define Versao    "1.2.3"
#define Publisher "Clauber Regis"
#define Exe       "VozFlow.exe"

[Setup]
AppId={{7C4A9F31-6E2D-4B58-9A17-2F8E5D0C3B41}
AppName={#Nome}
AppVersion={#Versao}
AppPublisher={#Publisher}
DefaultDirName={localappdata}\Programs\{#Nome}
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
OutputDir=instalador
OutputBaseFilename=VozFlow-{#Versao}-instalador
SetupIconFile=vozflow.ico
UninstallDisplayIcon={app}\{#Exe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"
Name: "startup";     Description: "Iniciar o {#Nome} junto com o Windows"; GroupDescription: "Inicializacao:"

[Files]
Source: "dist\{#Nome}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md";      DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#Nome}";                 Filename: "{app}\{#Exe}"
Name: "{group}\Desinstalar {#Nome}";     Filename: "{uninstallexe}"
; numa atualizacao nao recria o atalho que a pessoa tenha apagado
Name: "{autodesktop}\{#Nome}";           Filename: "{app}\{#Exe}"; Tasks: desktopicon; Check: not ReabrirDepois

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir o {#Nome} agora"; Flags: nowait postinstall skipifsilent
; Atualizacao automatica (/REABRIR=1, sempre silenciosa): abre a versao nova no fim
Filename: "{app}\{#Exe}"; Flags: nowait; Check: ReabrirDepois

[Code]
var
  Instalou: Boolean;        // chegou ao fim da copia dos arquivos
  AppNaoFechou: Boolean;    // desistiu porque o VozFlow continuou aberto

function ReabrirDepois(): Boolean;
begin
  Result := ExpandConstant('{param:REABRIR|0}') = '1';
end;

function InitializeSetup(): Boolean;
var
  espera: Integer;
begin
  Result := True;
  // Atualizacao automatica: o VozFlow dispara este instalador e fecha logo em
  // seguida. Copiar com ele ainda aberto falharia (arquivos em uso): espera a
  // trava de instancia unica (main.py) sumir, ate 30 s. Se nao sumir, desiste
  // sem tocar em nada - o VozFlow antigo segue aberto e funcionando.
  if ReabrirDepois() then
  begin
    espera := 0;
    while CheckForMutexes('Global\VozFlow_Singleton') and (espera < 60) do
    begin
      Sleep(500);
      espera := espera + 1;
    end;
    if CheckForMutexes('Global\VozFlow_Singleton') then
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
  // A atualizacao falhou no meio (disco cheio, antivirus...): o VozFlow ja
  // tinha fechado e o [Run] que reabre nao chegou a rodar. Abre de novo o que
  // estava instalado, em vez de deixar o usuario sem o app.
  voltar := ExpandConstant('{param:VOLTAR|}');
  if ReabrirDepois() and not Instalou and not AppNaoFechou and (voltar <> '') and FileExists(voltar) then
  begin
    Log('Atualizacao nao terminou; reabrindo ' + voltar);
    Exec(voltar, '', '', SW_SHOWNORMAL, ewNoWait, codigo);
  end;
end;

function CaminhoStartup(): String;
begin
  Result := ExpandConstant('{userstartup}\VozFlow.vbs');
end;

procedure GravarStartup();
var
  linhas: TArrayOfString;
  alvo: String;
begin
  alvo := ExpandConstant('{app}\VozFlow.exe');
  SetArrayLength(linhas, 2);
  linhas[0] := 'Set s = CreateObject("WScript.Shell")';
  linhas[1] := 's.Run """' + alvo + '""", 0, False';
  SaveStringsToFile(CaminhoStartup(), linhas, False);
end;

procedure CurStepChanged(passo: TSetupStep);
begin
  if passo = ssPostInstall then
  begin
    Instalou := True;
    // Numa atualizacao silenciosa a "tarefa" e a do ULTIMO instalador, mas o
    // proprio app liga e desliga o VozFlow.vbs depois disso (Configuracoes ->
    // Geral). Mexer aqui desfaria a escolha feita no app.
    if ReabrirDepois() then
      Exit;
    if WizardIsTaskSelected('startup') then
      GravarStartup()
    else
      DeleteFile(CaminhoStartup());
  end;
end;

procedure CurUninstallStepChanged(passo: TUninstallStep);
begin
  if passo = usPostUninstall then
  begin
    DeleteFile(CaminhoStartup());
    // Numa desinstalacao silenciosa nao ha ninguem para responder: o padrao
    // seguro e PRESERVAR a configuracao e o historico do usuario.
    if UninstallSilent() then
      Exit;
    if MsgBox('Apagar tambem suas configuracoes e o historico de transcricoes?' + #13#10 +
              '(pasta ' + ExpandConstant('{userappdata}\VozFlow') + ')',
              mbConfirmation, MB_YESNO) = IDYES then
      DelTree(ExpandConstant('{userappdata}\VozFlow'), True, True, True);
  end;
end;
