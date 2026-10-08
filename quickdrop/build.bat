@echo off
REM ============================================================
REM  QuickDrop build script - produces dist\QuickDrop.exe
REM  ASCII only on purpose: cmd.exe parses .bat as GBK, so any
REM  UTF-8 Chinese here would corrupt the batch control flow.
REM ============================================================
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [ERROR] venv python not found: "%PY%"
    echo         create it first:
    echo             python -m venv .venv
    echo             .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

echo [1/3] installing / verifying PyInstaller ...
"%PY%" -m pip install -q "pyinstaller>=6.0.0"
if errorlevel 1 goto err

echo [2/3] building QuickDrop.exe ^(onefile^) ...
"%PY%" -m PyInstaller --noconfirm --clean QuickDrop.spec
if errorlevel 1 goto err

echo [3/3] done.
echo.
echo Result: "%~dp0dist\QuickDrop.exe"
echo Note  : config.json / received\ / shared\ / logs\ will be created
echo         NEXT TO the exe on first run.
exit /b 0

:err
echo.
echo [FAILED] build aborted - see messages above.
exit /b 1
