@echo off
echo ========================================
echo   Sweetsnipe Hosted - Startup Script
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed. Please install Python 3.10+
    pause
    exit /b 1
)

REM Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt
pip install -r web/requirements.txt

REM Generate keys if not exists
if not exist "web\.env" (
    echo [2/3] Generating encryption keys...
    python -c "from cryptography.fernet import Fernet; import secrets; f=open('web\.env','w'); f.write('SECRET_KEY=' + secrets.token_hex(32) + '\n'); f.write('ENCRYPTION_KEY=' + Fernet.generate_key().decode() + '\n'); f.close()"
    echo Generated web\.env
) else (
    echo [2/3] web\.env already exists, skipping.
)

REM Start server
echo [3/3] Starting server...
echo.
echo Access the dashboard at: http://localhost:8000
echo.
cd web
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
