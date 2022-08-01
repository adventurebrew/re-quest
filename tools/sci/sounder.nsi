;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"

;--------------------------------
;General

  ;Name and file
  Name "Sounder"
  OutFile "dist\Sounder Installer.exe"
  Unicode True

  BrandingText "(C) Zvika Haramaty"

  ;Default installation folder
  InstallDir "$PROGRAMFILES\Sounder"

  ;Get installation folder from registry if available
  InstallDirRegKey HKCU "Software\Sounder" ""

  ;Request application privileges for Windows Vista
  RequestExecutionLevel admin  ;Z user

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING


  ; run at end
  !define MUI_FINISHPAGE_RUN "$INSTDIR\Sounder.exe"


;--------------------------------
;Pages

  !insertmacro MUI_PAGE_WELCOME			;Z ?
;Z  !insertmacro MUI_PAGE_LICENSE "${NSISDIR}\Docs\Modern UI\License.txt"
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
  !insertmacro MUI_PAGE_FINISH

  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
;Languages

  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section "Sounder" SecMain

  ; make section mandatory - no opt out
  SectionIn RO

  SetOutPath "$INSTDIR"

  ;ADD YOUR OWN FILES HERE...
  File /r "dist\Sounder\*"

  ;Store installation folder
  WriteRegStr HKCU "Software\Sounder" "" $INSTDIR

  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ;create start-menu items
  CreateDirectory "$SMPROGRAMS\Sounder"
  CreateShortCut "$SMPROGRAMS\Sounder\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
  CreateShortCut "$SMPROGRAMS\Sounder\Sounder.lnk" "$INSTDIR\Sounder.exe" "" "$INSTDIR\Sounder.exe" 0


SectionEnd

Section "Create desktop shortcut" SecDesktop
  ;create desktop shortcut
  CreateShortCut "$DESKTOP\Sounder.lnk" "$INSTDIR\Sounder.exe" ""
SectionEnd


;--------------------------------
;Descriptions

  ;Language strings
  LangString DESC_SecMain ${LANG_ENGLISH} "Sounder core component."
  LangString DESC_SecDesktop ${LANG_ENGLISH} "Create a desktop shortcut for Sounder."

  ;Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_SecDesktop)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  ;ADD YOUR OWN FILES HERE...

  Delete "$INSTDIR\Uninstall.exe"

  RMDir /r "$INSTDIR"

  ;Delete Desktop and Start Menu Shortcuts
  Delete "$DESKTOP\Sounder.lnk"
  Delete "$SMPROGRAMS\Sounder\*.*"
  RmDir  "$SMPROGRAMS\Sounder"


  DeleteRegKey /ifempty HKCU "Software\Sounder"

SectionEnd