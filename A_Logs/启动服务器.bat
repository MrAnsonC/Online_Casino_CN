@echo off
cd /d "%~dp0"
start /b php -S localhost:8000
timeout /t 2 >nul
start http://localhost:8000
pause