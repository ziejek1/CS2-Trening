#define MyAppName "CS2 Trening E-Sport"
#define MyAppVersion "1.0.11"
#define MyAppPublisher "CS2 Trening"
#define MyAppExeName "CS2Trening.exe"

[Setup]
AppId={{A2D9C2B9-22D4-4AA4-9C72-CS2TRENING}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CS2Trening
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=CS2Trening-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
CloseApplicationsFilter=CS2Trening.exe
RestartApplications=no

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "Utwórz skrót na pulpicie"; GroupDescription: "Dodatkowe skróty:"

[Files]
Source: "..\dist\CS2Trening\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\users.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "..\pro_training_data.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "..\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Uruchom {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Dane użytkownika celowo nie są usuwane podczas odinstalowania.
Type: filesandordirs; Name: "{app}\_internal"
