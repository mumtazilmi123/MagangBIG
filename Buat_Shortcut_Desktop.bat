@echo off
title Membuat Shortcut Veridoc di Desktop
echo ===================================================
echo   Membuat Shortcut Desktop untuk Veridoc Web App...
echo ===================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [System.Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut(\"$desktop\Veridoc Web App.lnk\"); $s.TargetPath = '%~dp0Buka_Veridoc.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,14'; $s.Description = 'Veridoc - Sistem Audit SKVT & Koordinat Spasial BIG'; $s.Save()"

echo [SUKSES] Shortcut "Veridoc Web App.lnk" telah berhasil dibuat di Desktop!
echo Anda dapat klik ganda ikon "Veridoc Web App" di Desktop untuk membuka aplikasi.
ping 127.0.0.1 -n 3 >nul
