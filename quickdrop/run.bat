@echo off
REM ============================================================
REM  QuickDrop dev launcher
REM  Starts the server + GUI window. ASCII only on purpose:
REM  cmd.exe parses .bat as GBK, so UTF-8 Chinese here would
REM  corrupt the batch control flow.
REM ============================================================
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [ERROR] venv python not found: "%PY%"
    echo.
    echo   create it first:
    echo       python -m venv .venv
    echo       .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Starting QuickDrop ... a window will pop up showing the QR code.
echo Close the window to stop the server.
echo.
"%PY%" server.py

if errorlevel 1 (
    echo.
    echo [ERROR] server exited with an error. See logs\quickdrop.log
    pause
)
exit /b 0
