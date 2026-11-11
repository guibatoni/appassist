@echo off
setlocal
cd /d "%~dp0"
title DUELTRACE - Gerar ZIP Windows local (nao assinado)
echo ============================================================
echo Gerar ZIP Windows local (nao assinado)
echo ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\release\assistente_windows.ps1" -Acao Compilar
if errorlevel 1 (
  echo.
  echo [ERRO] Processo interrompido. Confira as mensagens acima.
  pause
  exit /b 1
)
echo.
echo [OK] Etapa finalizada. Consulte as mensagens acima.
pause
endlocal
