rd /s /q dist

pyinstaller sounder.py ^
    --clean ^
    --noconfirm ^
    --paths . ^
    --noconsole ^
    --dist dist/gui ^
    --exclude-module numpy ^
    --exclude-module pil ^
    --add-data misc;misc ^
    --icon "misc/sounder.ico"

pyinstaller sounder.py ^
    --clean ^
    --noconfirm ^
    --paths . ^
    --console ^
    --dist dist/cli ^
    --exclude-module numpy ^
    --exclude-module pil ^
    --add-data misc;misc ^
    --icon "misc/sounder.ico"


"C:\Program Files (x86)\NSIS\Bin\makensis.exe" sounder.nsi

"dist\Sounder Installer.exe"


