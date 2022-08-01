pyinstaller sounder.py ^
    --clean ^
    --noconfirm ^
    --paths . ^
    --noconsole ^
    --exclude-module numpy ^
    --exclude-module pil

"C:\Program Files (x86)\NSIS\Bin\makensis.exe" sounder.nsi

"dist\Sounder Installer.exe"


