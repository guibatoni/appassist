@echo off
setlocal
cd /d "%~dp0"
title DUELTRACE - Assinar, auditar e publicar ZIP Windows apos aprovacoes
echo ============================================================
echo Assinar, auditar e publicar ZIP Windows apos aprovacoes
echo ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\release\assistente_windows.ps1" -Acao Publicar
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
