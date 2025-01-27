@echo off

rem Check if a file was dropped
if "%~1" == "" goto end

call .venv\Scripts\activate.bat

rem echo Checking Python path...
rem where python

rem Run the Python script
"E:\Github\resize-image-zipfile\.venv\Scripts\python.exe" "script.py" "%~1"


rem Keep the command prompt window open until a key is pressed
echo.
echo Press any key to exit...
pause > nul
goto end

:end