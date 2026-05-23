#define MyAppName "MaintiQ Predict Lite"
#define MyAppVersion "1.1.1"
#define MyAppPublisher "MaintiQ"
#define MyAppExeName "MaintiQ_Predict_Lite.exe"

[Setup]
AppId={{9C6C3CF5-7332-4B48-AE19-0A9E18899A12}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/HwangYH98/capstone-design-ai4i-genai-spc
AppSupportURL=https://github.com/HwangYH98/capstone-design-ai4i-genai-spc/issues
AppUpdatesURL=https://github.com/HwangYH98/capstone-design-ai4i-genai-spc/releases
DefaultDirName={localappdata}\Programs\MaintiQ Predict Lite
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=MaintiQ_Predict_Lite_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\MaintiQ_Predict_Lite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\DISTRIBUTION_POLICY.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\CODE_SIGNING_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\FIELD_VALIDATION_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\outputs\operations.db"
Type: files; Name: "{app}\outputs\operations_lite.db"
Type: files; Name: "{app}\outputs\field_validation_report.csv"
Type: files; Name: "{app}\outputs\field_validation_report.json"
Type: files; Name: "{app}\outputs\field_validation_report.md"
Type: files; Name: "{app}\outputs\*screenshot*.png"
Type: files; Name: "{app}\outputs\lite_prediction_results.csv"
Type: filesandordirs; Name: "{app}\outputs\realtime_stream"
Type: filesandordirs; Name: "{app}\outputs\work_order_drafts"
