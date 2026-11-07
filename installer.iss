; installer.iss
#define MyAppName "Core V3.0"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Сильченко Алексей"
#define MyAppExeName "Core_V3_0.exe"
#define MyAppSource "dist\Core_V3_0\*"

[Setup]
; Уникальный ID приложения (сгенерирован через Tools -> Generate GUID)
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Устанавливаем в папку пользователя (LocalAppData)
DefaultDirName={localappdata}\{#MyAppName}
DisableProgramGroupPage=yes
; Куда сохранить готовый Setup.exe
OutputDir=installer
OutputBaseFilename=Core_V3_0_Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Требуем минимальные права (без администратора)
PrivilegesRequired=lowest
; Архитектура (64-битная)
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Копируем всё из папки, собранной PyInstaller
Source: "{#MyAppSource}"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Ярлык в меню Пуск (для текущего пользователя)
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Ярлык на рабочем столе (для текущего пользователя)
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Запустить программу после установки
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent