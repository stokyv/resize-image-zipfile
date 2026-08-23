@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
pushd "%~dp0"

if "%~1"=="" (
    echo Drop one or more ZIP, CBZ, or RAR files onto this batch file.
    goto finish
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python environment not found at "%CD%\.venv".
    goto finish
)

".venv\Scripts\python.exe" "script.py" %*

:finish
popd
echo.
echo Press any key to exit...
pause >nul
endlocal
