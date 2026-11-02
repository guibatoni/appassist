@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 gerenciador_mods.py
) else (
    python gerenciador_mods.py
)
if errorlevel 1 (
    echo.
    echo Falha ao iniciar. Instale Python 3.10+ e Pillow para exportar artes.
    pause
)
