@echo off
where pyw >nul 2>nul || goto nopython
start "" pyw "%~dp0tools\tron_launcher.py"
exit /b
:nopython
echo Python was not found. Install it from https://www.python.org/downloads/
echo with the installer's default options, then run this again.
pause
