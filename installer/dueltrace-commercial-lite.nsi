; DUELTRACE Commercial Lite — INSTALADOR EXPERIMENTAL (não distribuir sem revisão).
; Build manual: makensis /DBUILD_DIR="C:\...\dist\DUELTRACE-WebUI" installer\dueltrace-commercial-lite.nsi
; NSIS (zlib/libpng & other permissive licenses). No administrator rights.
; Previous install location persists, preventing duplicate installation directories.

Unicode true
!include "MUI2.nsh"

!ifndef BUILD_DIR
  !error "Informe /DBUILD_DIR com a pasta real do PyInstaller."
!endif
!if /FileExists "${BUILD_DIR}\DUELTRACE-WebUI.exe"
!else
  !error "DUELTRACE-WebUI.exe não encontrado na pasta BUILD_DIR."
!endif
!if /FileExists "${BUILD_DIR}\_internal\dueltrace-build.json"
!else
  !error "Identidade de compilação ausente em _internal."
!endif

Name "DUELTRACE — Batoni Dev (Prévia comercial)"
OutFile "DUELTRACE-Setup-TESTE.exe"
InstallDir "$LOCALAPPDATA\Programs\DUELTRACE"
InstallDirRegKey HKCU "Software\BatoniDev\DUELTRACE" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show
BrandingText "Batoni Dev — DUELTRACE"

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

Function .onInit
  ; An existing install has precedence over the default: no second folder.
  ReadRegStr $0 HKCU "Software\BatoniDev\DUELTRACE" "InstallLocation"
  StrCmp $0 "" done
    StrCpy $INSTDIR $0
  done:
FunctionEnd

Section "DUELTRACE" SEC_MAIN
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  SetOverwrite on

  ; Include only the reviewed PyInstaller output, never ISO, keys or user data.
  File /r "${BUILD_DIR}\*"

  WriteUninstaller "$INSTDIR\Desinstalar DUELTRACE.exe"
  CreateDirectory "$SMPROGRAMS\Batoni Dev"
  CreateShortcut "$SMPROGRAMS\Batoni Dev\DUELTRACE.lnk" "$INSTDIR\DUELTRACE-WebUI.exe"
  CreateShortcut "$SMPROGRAMS\Batoni Dev\Desinstalar DUELTRACE.lnk" "$INSTDIR\Desinstalar DUELTRACE.exe"

  WriteRegStr HKCU "Software\BatoniDev\DUELTRACE" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE" "DisplayName" "DUELTRACE — Batoni Dev"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE" "DisplayVersion" "0.9.7"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE" "Publisher" "Batoni Dev"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE" "UninstallString" '$\"$INSTDIR\Desinstalar DUELTRACE.exe$\"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  ; Delete app-owned files only. AppData, ISOs, saves and unknown user files stay.
  Delete "$SMPROGRAMS\Batoni Dev\DUELTRACE.lnk"
  Delete "$SMPROGRAMS\Batoni Dev\Desinstalar DUELTRACE.lnk"
  RMDir "$SMPROGRAMS\Batoni Dev"

  Delete "$INSTDIR\DUELTRACE-WebUI.exe"
  Delete "$INSTDIR\LEIA-ME-SEGURANCA.txt"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\Desinstalar DUELTRACE.exe"
  RMDir "$INSTDIR"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DUELTRACE"
  DeleteRegKey HKCU "Software\BatoniDev\DUELTRACE"
SectionEnd
