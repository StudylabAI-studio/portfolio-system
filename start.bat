@echo off
echo ============================================
echo  Starting Portfolio System...
echo ============================================
echo.

cd /d "%~dp0"

python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python.
    pause
    exit /b
)

if not exist "venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo [SETUP] Installing dependencies...
pip install -r requirements.txt -q

python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.stop()" > nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing Playwright browsers...
    playwright install chromium
)

echo.
echo [START] Opening browser...
echo [INFO]  Press Ctrl+C or close this window to stop the server.
echo.
streamlit run app.py --server.port 8502 --browser.gatherUsageStats false

pause
