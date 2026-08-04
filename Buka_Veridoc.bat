@echo off
title Veridoc - Sistem Audit SKVT BIG
echo ===================================================
echo   Memulai Veridoc Web App...
echo ===================================================

cd /d "%~dp0backend"

netstat -ano | findstr :8000 >nul 2>&1
if %errorlevel% equ 0 (
    echo Server Veridoc sudah aktif pada port 8000.
) else (
    echo Menjalankan server backend Veridoc...
    start /b python -m uvicorn main:app --host 127.0.0.1 --port 8008 --reload --reload-exclude "*.duckdb" --reload-exclude "*.pdf"
    timeout /t 3 /nobreak >nul
)

echo Membuka Veridoc dalam mode aplikasi Desktop...
start msedge --app=http://127.0.0.1:8008/ 2>nul || start chrome --app=http://127.0.0.1:8008/ 2>nul || start http://127.0.0.1:8000/

exit
