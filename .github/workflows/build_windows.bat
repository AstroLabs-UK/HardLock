@echo off
echo Installing dependencies...
pip install -r requirements.txt pyinstaller pywin32
echo.
echo Building HardLock.exe with icon...
pyinstaller --onefile --windowed --name "HardLock" --icon=icon.png --clean app.py
echo.
echo Done! Look in the dist\ folder for HardLock.exe
pause
