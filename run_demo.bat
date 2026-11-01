@echo off
REM Legal AI Hub - one-click demo launcher (Windows)
REM Double-click this file, or run it from the project folder.

cd /d "%~dp0"

REM Use .venv if it exists (the one with the packages installed), otherwise venv
set "VENV_DIR="
if exist ".venv\Scripts\activate.bat" set "VENV_DIR=.venv"
if not defined VENV_DIR if exist "venv\Scripts\activate.bat" set "VENV_DIR=venv"
if not defined VENV_DIR (
    echo [ERROR] No virtual environment found in "%~dp0".
    echo Create it once with:  python -m venv .venv  ^&^&  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo Using virtual environment: %VENV_DIR%
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo Running demo readiness check...
python check_setup.py
if errorlevel 1 (
    echo.
    echo Some checks failed. Press any key to start the app anyway, or close this window to fix them first.
    pause >nul
)

echo.
echo Starting Legal AI Hub at http://localhost:8501  (close this window to stop it)
python -m streamlit run app.py --server.headless false
