@echo off
title Audit Peta Batas Desa — BIG Template
color 0A
cls

echo ============================================================
echo   AUDIT PETA BATAS DESA — Template BIG
echo   Sistem Pemeriksaan 16 Komponen Kartografi
echo ============================================================
echo.

:: Pindah ke direktori root project
cd /d "%~dp0"

:: Cek Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan. Pastikan Python 3.9+ sudah terinstall.
    pause
    exit /b 1
)

:: Cek apakah server sudah berjalan di port 8001
netstat -ano | findstr ":8001" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Server sudah berjalan di port 8001.
    echo [INFO] Membuka dashboard...
    start "" "http://localhost:8001"
    pause
    exit /b 0
)

echo [INFO] Memulai server Audit Peta Batas Desa di port 8001...
echo [INFO] Dashboard akan terbuka otomatis di browser.
echo [INFO] Tekan Ctrl+C untuk menghentikan server.
echo.

:: Buka browser setelah 3 detik
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8001"

:: Jalankan server
cd backend
python -m uvicorn peta_audit.main_peta:app --host 0.0.0.0 --port 8001 --reload

pause
