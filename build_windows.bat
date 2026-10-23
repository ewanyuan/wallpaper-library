@echo off
setlocal
cd /d "%~dp0"
if exist ".build-venv" rmdir /s /q ".build-venv"
python -m venv .build-venv
if errorlevel 1 exit /b 1
set "PY=%~dp0.build-venv\Scripts\python.exe"
"%PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%PY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1
"%PY%" -m PyInstaller --noconfirm --clean WallpaperLibrary.spec
if errorlevel 1 exit /b 1
echo.
echo Built dist\WallpaperLibrary\WallpaperLibrary.exe
endlocal
