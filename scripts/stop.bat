@echo off
chcp 65001 >nul
echo 停止AI学习诊断系统...
taskkill /f /fi "WINDOWTITLE eq AI-Backend*" 2>nul
taskkill /f /fi "WINDOWTITLE eq AI-Frontend*" 2>nul
taskkill /f /im python.exe /fi "WINDOWTITLE eq *uvicorn*" 2>nul
taskkill /f /im node.exe /fi "WINDOWTITLE eq *vite*" 2>nul
echo   系统已停止
pause
