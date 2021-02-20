# STOPPED DEV'ING, moved to PQ1 dir
# will return to this as template...
#
#
#
# "C:\Program Files (x86)\NSIS\Bin\GenPat.exe" C:\Zvika\Games\PoliceQuest\AGI.check\WORDS.TOK C:\Zvika\Games\PoliceQuest\AGI\WORDS.TOK WORDS.TOK.patch
# "C:\Program Files (x86)\NSIS\Bin\GenPat.exe" C:\Zvika\ames\PoliceQuest\AGI.check\LOGDIR C:\Zvika\Games\PoliceQuest\AGI\LOGDIR logdir.patch
# "C:\Program Files (x86)\NSIS\Bin\GenPat.exe" C:\Zvika\Games\PoliceQuest\AGI.check\VOL.0 C:\Zvika\Games\PoliceQuest\AGI\VOL.0 VOL.0.patch

!include MUI2.nsh

!macro BackupAndUpdateFile FILE 
    IfFileExists "${INSTDIR}\ORIG\*.*" +2
        CreateDirectory "${INSTDIR}\ORIG"
    IfFileExists "${INSTDIR}\ORIG\${FILE}" +2
        CopyFiles "${INSTDIR}\${FILE}" "${INSTDIR}\ORIG\${FILE}"
    ;TODO - check so far, if works well, move here the update code
!macroend


; The name of the installer
Name "התרגום העברי של PQ1"

# define installer name
OutFile "sq1-hebrew-installer.exe"
 
Unicode true

; The default installation directory
InstallDir "C:\Zvika\Games\PoliceQuest\AGI.check"  #TODO remove this

!define MUI_TEXT_WELCOME_INFO_TEXT "New text goes here$\r$\n \
and in new line" ;" ; gvim get's confused without that extra "

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "Hebrew"

; The text to prompt the user to enter a directory
DirText "בחר את התיקייה שקבצי PQ1 נמצאים בה"

!include "VPatchLib.nsh"

Section "Update file"
  ; Set output path to the installation directory
  SetOutPath $INSTDIR

  ; Extract the old file under name 'updatefile.txt'
  ;File /oname=updatefile.txt oldfile.txt
  
  ; Update the file - it will be replaced with the new version
  DetailPrint "Updating updatefile.txt using patch..."
  !insertmacro VPatchFile VOL.0.patch "$INSTDIR\VOL.0" "$INSTDIR\VOL.0.tmp"

IfErrors 0 +2
    abort
  ;MessageBox MB_OK "errors"
  
# define uninstaller name
WriteUninstaller $INSTDIR\uninstaller.exe
 
SectionEnd

# create a section to define what the uninstaller does.
# the section will always be named "Uninstall"
Section "Uninstall"
 
# now delete installed file
Delete $INSTDIR\test.txt

# Always delete uninstaller first
#Z why? it doesn't make sense to me
#Z what if the uninstaller is aborted in the middle of its work?
Delete $INSTDIR\uninstaller.exe
 
 
SectionEnd

