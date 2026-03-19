; Inno Setup script for LE Beta Particle Visualization

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppName=LE Beta Particle Visualization
AppVersion={#AppVersion}
AppPublisher=Oregon State University
AppPublisherURL=https://github.com/OSUCSVisualizationTeam/le-beta-particle-vis-lbnl
DefaultDirName={autopf}\LBNLVis
DefaultGroupName=LBNLVis
OutputDir=..\dist
OutputBaseFilename=LBNLVis-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
SetupIconFile=lbnlvis.ico

[Files]
Source: "..\dist\lbnlvis\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\LE Beta Particle Visualization"; Filename: "{app}\lbnlvis.exe"
Name: "{group}\Uninstall LBNLVis"; Filename: "{uninstallexe}"
Name: "{commondesktop}\LE Beta Particle Visualization"; Filename: "{app}\lbnlvis.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\lbnlvis.exe"; Description: "Launch LE Beta Particle Visualization"; Flags: nowait postinstall skipifsilent
