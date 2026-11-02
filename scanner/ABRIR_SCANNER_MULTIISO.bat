@echo off
setlocal
cd /d "%~dp0"
set /p "ISOS=Pasta com as ISOs (.bin/.iso): "
if not defined ISOS exit /b 1
py -3 "tools\scanner_multiiso.py" --entrada "%ISOS%" --saida "analises_multimod"
pause
