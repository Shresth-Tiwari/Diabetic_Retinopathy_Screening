@echo off
cd /d "%~dp0"
title RETINOVA

rem Use the project virtual environment (.venv) if present, otherwise the system Python.
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

rem Check the required packages before starting, so a missing one gives a clear message.
"%PYTHON%" -c "import fastapi, uvicorn, multipart, jinja2, PIL, numpy, torch, torchvision" 2>nul
if errorlevel 1 (
    echo Some required packages are missing. Install them with:
    echo     "%PYTHON%" -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting RETINOVA... the model takes a few seconds to load.
echo Open http://localhost:8000 in your browser. Press Ctrl+C to stop.
echo.

rem Open the browser once the server has had time to start.
start "" /b cmd /c "timeout /t 6 /nobreak >nul & start http://localhost:8000"

"%PYTHON%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
if errorlevel 1 pause
