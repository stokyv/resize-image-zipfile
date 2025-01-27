@echo off

rem Check if a file was dropped
call .venv\Scripts\activate.bat
if "%~1" == "" (
    rem No file dropped, run the Python script without arguments
    python "script.py"
) else (
    rem File dropped, run the Python script with the dropped file as an argument
    python "script.py" "%~1"
)

rem Keep the command prompt window open until a key is pressed
echo.
echo Press any key to exit...
pause > nul
