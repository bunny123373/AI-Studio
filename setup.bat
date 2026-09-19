@echo off
chcp 65001 >nul
title AI YouTube Studio - Setup (first time setup)
echo ==================================================
echo   AI YouTube Studio - Installing tools
echo   This runs ONCE. It needs an internet connection.
echo ==================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on this PC.
    echo Install it from https://www.python.org/downloads/
    echo IMPORTANT: during install tick  "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/2] Updating pip ...
python -m pip install --upgrade pip

echo.
echo [2/2] Installing packages. This may take several minutes ...
python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo [WARNING] Core install had a problem. Trying the smaller core set...
    python -m pip install pillow numpy imageio-ffmpeg deep-translator uharfbuzz freetype-py
)

echo.
echo Installing speech recognition for Tool 3 (subtitles) ...
python -m pip install faster-whisper
if errorlevel 1 (
    echo.
    echo [NOTE] faster-whisper could not be installed.
    echo Tools 1, 2, 4 and 5 still work normally.
    echo Tool 3 needs this package, internet, and some patience.
)

echo.
echo ==================================================
echo   Setup finished!
echo   Now double-click  studio.bat  to start.
echo ==================================================
pause