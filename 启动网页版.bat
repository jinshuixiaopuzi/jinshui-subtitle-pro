@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 金水字幕 Pro 网页版 — 启动中...

cd /d "%~dp0"

:: =================================================================
::  金水字幕 Pro — 网页版启动脚本
::  后端: Python FastAPI (端口 8712)
::  前端: Vite 开发服务器 (端口 5173) → 浏览器打开
:: =================================================================

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   金水字幕 Pro 网页版  启动中 ...        ║
echo   ╚══════════════════════════════════════════╝
echo.

:: =================================================================
:: 1. 检查 Python 虚拟环境
:: =================================================================
if not exist "venv\Scripts\python.exe" (
    echo [错误] 未找到 venv\Scripts\python.exe
    echo 请先创建虚拟环境并安装依赖
    pause
    exit /b 1
)

:: =================================================================
:: 2. 清理占用端口的旧进程（只清理 LISTENING 状态，不会误杀系统进程）
:: =================================================================
echo [清理] 检查旧进程...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8712"') do (
    set pid=%%a
    if not "!pid!"=="0" (
        echo    关闭旧后端进程 (PID: !pid!)
        taskkill /pid !pid! /f >nul 2>&1
    )
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":5173"') do (
    set pid=%%a
    if not "!pid!"=="0" (
        echo    关闭旧前端进程 (PID: !pid!)
        taskkill /pid !pid! /f >nul 2>&1
    )
)

timeout /t 1 /nobreak >nul

:: =================================================================
:: 3. 启动 API 后端
:: =================================================================
echo.
echo [1/2] 启动 AI 引擎后端...

start "金水字幕Pro-引擎" /MIN "venv\Scripts\python.exe" api_server.py

:: 等待端口就绪
set wait_count=0
:wait_engine
set /a wait_count+=1
if !wait_count! gtr 15 (
    echo [错误] 引擎启动超时（30 秒）
    echo    手动测试: venv\Scripts\python.exe api_server.py
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
netstat -ano 2>nul | findstr "LISTENING" | findstr ":8712" >nul 2>&1
if errorlevel 1 goto wait_engine
echo   [完成] API 引擎已就绪 (端口 8712)

:: =================================================================
:: 4. 启动前端 + 浏览器
:: =================================================================
echo.
echo [2/2] 启动前端界面...

pushd frontend

if not exist "node_modules" (
    echo    安装前端依赖...
    call npm install
    if errorlevel 1 (
        echo [错误] npm install 失败
        popd
        pause
        exit /b 1
    )
)

start "金水字幕Pro-前端" cmd /c "npx vite --strictPort --host"

:: 等待 Vite 就绪
set wait_count=0
:wait_frontend
set /a wait_count+=1
if !wait_count! gtr 20 (
    echo [信息] 前端仍在启动中，即将打开浏览器...
    goto open_browser
)
timeout /t 1 /nobreak >nul
netstat -ano 2>nul | findstr "LISTENING" | findstr ":5173" >nul 2>&1
if errorlevel 1 goto wait_frontend

:open_browser
popd
timeout /t 2 /nobreak >nul
start http://localhost:5173

:: =================================================================
:: 5. 完成
:: =================================================================
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   金水字幕 Pro 网页版  启动完成！        ║
echo   ╠══════════════════════════════════════════╣
echo   ║  API 后端 : http://127.0.0.1:8712        ║
echo   ║  前端界面 : http://localhost:5173        ║
echo   ╚══════════════════════════════════════════╝
echo.
echo 按任意键退出（将关闭引擎和前端服务器）...
pause >nul

echo 正在关闭后台进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8712"') do (
    taskkill /pid %%a /f >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":5173"') do (
    taskkill /pid %%a /f >nul 2>&1
)

endlocal
exit /b 0
