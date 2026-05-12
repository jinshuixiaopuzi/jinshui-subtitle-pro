[Setup]
AppId={{8F6E2D4A-9B3C-4A7E-8D1F-5C6B7A8E9D0F}
AppName=金水字幕 Pro
AppVersion=2.0.0
AppPublisher=Jinshui
AppPublisherURL=https://github.com/jinshui
DefaultDirName={userpf}\金水字幕 Pro
DefaultGroupName=金水字幕 Pro
OutputDir=E:\Jinshui_Pro\dist
OutputBaseFilename=金水字幕Pro_Setup_v2.0.0
Compression=lzma2
SolidCompression=no
DiskSpanning=yes
DiskSliceSize=max
SlicesPerDisk=1
WizardStyle=modern
WizardSizePercent=100,100
SetupIconFile=E:\Jinshui_Pro\frontend\src-tauri\icons\icon.ico
UninstallDisplayIcon={app}\app.exe
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
VersionInfoVersion=2.0.0
MinVersion=10.0

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "E:\Jinshui_Pro\frontend\src-tauri\target\release\app.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "E:\Jinshui_Pro\_tauri_staging\engine\*"; DestDir: "{app}\engine"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\金水字幕 Pro"; Filename: "{app}\app.exe"
Name: "{autodesktop}\金水字幕 Pro"; Filename: "{app}\app.exe"

[Run]
Filename: "{app}\app.exe"; Description: "{cm:LaunchProgram,金水字幕 Pro}"; Flags: nowait postinstall skipifsilent
