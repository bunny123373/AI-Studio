@echo off
chcp 65001 >nul
title AI YouTube Studio - Web (browser UI)
cd /d "%~dp0"
python webapp.py
echo.
pause