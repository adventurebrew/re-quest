rd /s /q dist

rem might be improved if https://github.com/pyinstaller/pyinstaller/issues/7020 will be added

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
    --dist dist/both ^
    --exclude-module numpy ^
    --exclude-module pil ^
    --add-data misc;misc ^
    --icon "misc/sounder.ico"

copy "dist\gui\sounder\sounder.exe" "dist\both\sounder\sounder_no_console.exe"

"C:\Program Files (x86)\NSIS\Bin\makensis.exe" sounder.nsi

"dist\Sounder Installer.exe"


