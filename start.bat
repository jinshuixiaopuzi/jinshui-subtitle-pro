@echo off
cd /d "%~dp0"

:: Kill old processes
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8712"') do (
    taskkill /pid %%a /f >nul 2>&1
)

:: Start API backend
start "API" /MIN "venv\Scripts\python.exe" api_server.py

:: Wait for API
:wait
timeout /t 2 /nobreak >nul
netstat -ano 2>nul | findstr "LISTENING" | findstr ":8712" >nul 2>&1
if errorlevel 1 goto wait

:: Start Tauri desktop app
cd frontend
start "Jinshui Pro" cmd /c "npx tauri dev"
cd ..
