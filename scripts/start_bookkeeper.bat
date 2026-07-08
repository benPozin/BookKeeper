@echo off
setlocal
cd /d "%~dp0\.."

if not exist "data\logs" mkdir "data\logs"

if not exist "backend\.venv" (
    echo Creating Python virtual environment...
    python -m venv backend\.venv
    call backend\.venv\Scripts\activate.bat
    pip install -r backend\requirements.txt
) else (
    call backend\.venv\Scripts\activate.bat
)

if not exist "frontend\dist\index.html" (
    echo Building the frontend for the first time...
    pushd frontend
    call npm install
    call npm run build
    popd
)

echo Starting BookKeeper on http://localhost:8765 ...
start "" http://localhost:8765

cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8765 >> ..\data\logs\server.log 2>&1
