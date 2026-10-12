@echo off
REM Legal AI Hub - one-click demo launcher (Windows)
REM Double-click this file, or run it from the project folder.

cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] No virtual environment found in "%~dp0venv".
    echo Create it once with:  python -m venv venv  ^&^&  venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"

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
