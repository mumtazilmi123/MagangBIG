@echo off
title SIPETIK - Pembuat Link Publik
color 0A

echo ===================================================
echo     SIPETIK - Pembuat Terowongan Internet Gratis
echo ===================================================
echo.
echo 1. Menyalakan mesin server di latar belakang...
cd /d "%~dp0\backend"
start /b python -m uvicorn main:app --host 0.0.0.0 --port 8000 >nul 2>&1

:: Beri waktu 3 detik agar server uvicorn menyala sempurna
timeout /t 3 /nobreak >nul

echo 2. Mesin menyala! Menghubungkan ke Internet Global...
echo.
echo Tunggu beberapa detik, URL publik Anda akan muncul berakhiran (.lhr.life)
echo Silakan COPY URL tersebut dan kirim ke teman Anda!
echo.
echo ===================================================
echo JANGAN TUTUP JENDELA HITAM INI SELAMA TEMAN ANDA MENGAKSES WEB
echo ===================================================
echo.

ssh -R 80:127.0.0.1:8000 nokey@localhost.run

pause
