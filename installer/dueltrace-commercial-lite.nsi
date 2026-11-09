; DUELTRACE Commercial Lite — INSTALADOR EXPERIMENTAL (não distribuir sem revisão).
; Build manual: makensis /DBUILD_DIR="C:\...\dist\DUELTRACE-WebUI" installer\dueltrace-commercial-lite.nsi
; NSIS (zlib/libpng & other permissive licenses). No administrator rights.
; Previous install location persists, preventing duplicate installation directories.

Unicode true
!include "MUI2.nsh"

!ifndef BUILD_DIR
  !error "Informe /DBUILD_DIR com a pasta real do PyInstaller."
!endif
!if /FileExists "${BUILD_DIR}\DUELTRACE-Commercial.exe"
!else
  !error "DUELTRACE-Commercial.exe não encontrado na pasta BUILD_DIR."
!endif
!if /FileExists "${BUILD_DIR}\_internal\dueltrace-build.json"
!else
  !error "Identidade de compilação ausente em _internal."
!endif

Name "DUELTRACE Commercial Lite — Batoni Dev (TESTE)"
OutFile "DUELTRACE-Setup-TESTE.exe"
InstallDir "$LOCALAPPDATA\Programs\DUELTRACE-Commercial"
; Fixed installation target: do not trust potentially unsafe registry paths.
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show
BrandingText "Batoni Dev — DUELTRACE"

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

Section "DUELTRACE" SEC_MAIN
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  SetOverwrite on

  ; Include only the reviewed PyInstaller output, never ISO, keys or user data.
  File /r "${BUILD_DIR}\*"

  WriteUninstaller "$INSTDIR\Desinstalar DUELTRACE.exe"
  CreateDirectory "$SMPROGRAMS\Batoni Dev"
  CreateShortcut "$SMPROGRAMS\Batoni Dev\DUELTRACE Commercial Lite.lnk" "$INSTDIR\DUELTRACE-Commercial.exe"
  CreateShortcut "$SMPROGRAMS\Batoni Dev\Desinstalar DUELTRACE Commercial.lnk" "$INSTDIR\Desinstalar DUELTRACE.exe"

  WriteRegStr HKCU "Software\BatoniDev\DUELTRACE-Commercial" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE-Commercial" "DisplayName" "DUELTRACE Commercial Lite — Batoni Dev (TESTE)"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE-Commercial" "DisplayVersion" "0.9.7"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE-Commercial" "Publisher" "Batoni Dev"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE-Commercial" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE-Commercial" "UninstallString" '$\"$INSTDIR\Desinstalar DUELTRACE.exe$\"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE-Commercial" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE-Commercial" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  ; Delete app-owned files only. AppData, ISOs, saves and unknown user files stay.
  Delete "$SMPROGRAMS\Batoni Dev\DUELTRACE Commercial Lite.lnk"
  Delete "$SMPROGRAMS\Batoni Dev\Desinstalar DUELTRACE Commercial.lnk"
  RMDir "$SMPROGRAMS\Batoni Dev"

  Delete "$INSTDIR\DUELTRACE-Commercial.exe"
  Delete "$INSTDIR\LEIA-ME-SEGURANCA.txt"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\Desinstalar DUELTRACE.exe"
  RMDir "$INSTDIR"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE-Commercial"
  DeleteRegKey HKCU "Software\BatoniDev\DUELTRACE-Commercial"
SectionEnd
