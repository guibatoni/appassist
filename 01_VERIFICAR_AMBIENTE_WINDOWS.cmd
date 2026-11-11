@echo off
setlocal
cd /d "%~dp0"
title DUELTRACE - Verificar Python, Node, Git e arquivos do projeto
echo ============================================================
echo Verificar Python, Node, Git e arquivos do projeto
echo ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\release\assistente_windows.ps1" -Acao Verificar
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
