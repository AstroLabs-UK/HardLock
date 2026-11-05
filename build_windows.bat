@echo off
echo Installing dependencies...
pip install -r requirements.txt pyinstaller pywin32
echo.
echo Building HardLock.exe ...
REM Use --uac-admin only. Do NOT also pass --manifest (causes SxS errors).
pyinstaller --onefile --windowed --name "HardLock" --icon=icon.png --uac-admin --clean app.py
echo.
echo Done! Look in the dist\ folder for HardLock.exe
echo The EXE will request Administrator privileges on launch.
pause
