@echo off
setlocal

REM Check if path argument is provided
if "%~1"=="" (
    echo Error: Please provide a path argument
    echo Usage: %~nx0 [path]
    exit /b 1
)

set "PATH_ARG=%~1"

echo Creating Python virtual environment...
IF NOT EXIST ".venv\Scripts\pip.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment
        exit /b 1
    )
)

echo Installing requirements...
.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements
    exit /b 1
)

echo Starting video server...
.venv\Scripts\python.exe main.py "%PATH_ARG%"
if errorlevel 1 (
    echo Video server exited with error
    exit /b 1
)

endlocal