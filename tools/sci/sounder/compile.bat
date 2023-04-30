rd /s /q build
rd /s /q dist

pyinstaller sounder.spec

"C:\Program Files (x86)\NSIS\Bin\makensis.exe" sounder.nsi

"dist\Sounder Installer.exe"


