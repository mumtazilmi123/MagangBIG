# Sistem Audit Geospasial Otomatis (BIG)

Aplikasi web tingkat instansi untuk memvalidasi transformasi koordinat geografis (WGS 84 ke UTM Krüger-Redfearn) dan memverifikasi kodifikasi wilayah administrasi (Permendagri No. 137) yang diekstrak langsung dari dokumen PDF resmi.

## Fitur Utama
- **Ekstraksi Cerdas (Regex Parser)**: Mengekstrak Titik Kartometrik secara akurat dari file PDF yang kotor/berantakan.
- **Engine Geospasial (pyproj)**: Transformasi proyeksi dinamis dari berbagai Datum geografis (WGS84 Epochs, SRGI2013, dll) ke zona UTM secara *per-titik*.
- **Validasi Tata Nama**: Verifikasi struktur kodifikasi hierarki (Provinsi > Kab/Kota > Kecamatan > Desa/Kel).
- **Laporan PDF Dinamis**: Auto-generate dokumen analitik PDF profesional (menggunakan Platypus) dengan statistik akurasi (dX, dY).
- **Frontend Elegan**: Antarmuka kelas korporasi dengan UI/UX yang responsif, mulus, dan terintegrasi `Select2`.

## Prasyarat Server
- Python 3.9+
- OS: Linux (disarankan) atau Windows

## Struktur Direktori
```
Web_Audit_App/
│
├── backend/
│   ├── main.py            # API Server (FastAPI)
│   ├── audit_engine.py    # Logika Spasial & Generator PDF
│   └── ...
│
├── frontend/
│   ├── index.html         # UI Utama
│   ├── styles.css         # Styling (BIG Blue Theme)
│   └── script.js          # Client-side Logic (Select2 & Ajax)
│
└── requirements.txt       # Dependencies Python
```

## Instalasi & Menjalankan (Deployment)

1. **Install Dependencies**
   Buka terminal di folder root (`Web_Audit_App`) dan jalankan:
   ```bash
   pip install -r requirements.txt
   ```

2. **Menyalakan Server**
   Ubah direktori ke folder `backend` dan jalankan server *uvicorn*:
   ```bash
   cd backend
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   *(Gunakan `--host 0.0.0.0` jika dihosting di VPS agar bisa diakses dari luar).*

3. **Akses Aplikasi**
   Buka browser dan arahkan ke alamat server/VPS Anda (contoh: `http://localhost:8000`).

## Credit
Dikembangkan oleh:
- Abidzar Al Ghifari
- Naufal Mumtaz Ilmi
