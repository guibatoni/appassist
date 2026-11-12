@echo off
setlocal
cd /d "%~dp0"
title DUELTRACE Cloud - Chrome local
echo.
echo ===================================================
echo   DUELTRACE CLOUD - ABRIR NO NAVEGADOR
echo ===================================================
echo.
echo O Connector vai abrir o navegador automaticamente.
echo Sem PowerShell, sem Node.js e sem copiar chaves.
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "scanner\dueltrace_cloud_connector.py" --browser
  goto :done
)
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" "scanner\dueltrace_cloud_connector.py" --browser
  goto :done
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "scanner\dueltrace_cloud_connector.py" --browser
  goto :done
)
where python >nul 2>nul
if not errorlevel 1 (
  python "scanner\dueltrace_cloud_connector.py" --browser
  goto :done
)
echo [ERRO] Python nao encontrado. Instale Python ou use o executavel
echo        do DUELTRACE quando o pacote Windows estiver pronto.
:done
echo.
echo Connector encerrado. Se ocorreu um erro, veja a mensagem acima.
pause
endlocal
