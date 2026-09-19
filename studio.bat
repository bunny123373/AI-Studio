@echo off
chcp 65001 >nul
title AI YouTube Studio
cd /d "%~dp0"
python studio.py
echo.
pause