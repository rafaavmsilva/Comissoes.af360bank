#define MyAppName "Sistema de Comissoes"
#define MyAppVersion "1.0.4"
#define MyAppPublisher "AF 360 PAY"
#define MyAppExeName "desktop.py"
#define PythonVersion "3.9.7"
#define PythonDir "{localappdata}\Programs\Python\Python39"

[Setup]
AppId={{B8A8DA53-7F89-45E1-9859-6D83AFE7CA94}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=output
OutputBaseFilename=SistemaComissoes_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableProgramGroupPage=yes

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Iniciar automaticamente com o Windows"; GroupDescription: "Outras opções:"; Flags: unchecked

[Files]
Source: "app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "desktop.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "system_tray.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "logs\*"; DestDir: "{app}\logs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "pythonw.exe"; Parameters: """{app}\{#MyAppExeName}"""; WorkingDir: "{app}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "pythonw.exe"; Parameters: """{app}\{#MyAppExeName}"""; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "pythonw.exe"; Parameters: """{app}\{#MyAppExeName}"""; WorkingDir: "{app}"; Tasks: startupicon

[Run]
; Install Python if not present
Filename: "https://www.python.org/ftp/python/3.9.7/python-3.9.7-amd64.exe"; Parameters: "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0 InstallLauncherAllUsers=1"; Check: PythonNotInstalled; Flags: shellexec waituntilterminated
; Wait for Python installation to complete
Filename: "{cmd}"; Parameters: "/c timeout /t 10"; Flags: runhidden waituntilterminated; Check: PythonNotInstalled
; Install pip if not present
Filename: "{cmd}"; Parameters: "/c python -m ensurepip --upgrade"; Flags: runhidden waituntilterminated
; Upgrade pip
Filename: "{cmd}"; Parameters: "/c ""{#PythonDir}\python.exe"" -m pip install --upgrade pip"; Flags: runhidden waituntilterminated
; Install requirements with specific versions
Filename: "{cmd}"; Parameters: "/c ""{#PythonDir}\python.exe"" -m pip install -r ""{app}\requirements.txt"" --no-cache-dir"; Flags: runhidden waituntilterminated
; Launch app after installation
Filename: "pythonw.exe"; Parameters: """{app}\{#MyAppExeName}"""; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Dirs]
Name: "{app}\logs"; Permissions: users-modify
Name: "{app}\uploads"; Permissions: users-modify

[Code]
function PythonNotInstalled: Boolean;
var
  PythonPath: String;
begin
  if RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SOFTWARE\Python\PythonCore\3.9\InstallPath',
    '', PythonPath) then
  begin
    Result := False;
  end else
  begin
    Result := True;
  end;
end;

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM pythonw.exe"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c rmdir /s /q ""{app}"""; Flags: runhidden