# Menggunakan base image Python versi 3.9 yang ringan
FROM python:3.9-slim

# Menentukan direktori kerja di dalam container
WORKDIR /app

# Meng-copy file requirements.txt ke dalam container
COPY requirements.txt .

# Menginstal dependensi (tanpa menyimpan cache agar ukuran container kecil)
RUN pip install --no-cache-dir -r requirements.txt

# Meng-copy seluruh kode aplikasi ke dalam container
COPY . .

# Mengekspos port 7860 (Standar port wajib untuk Hugging Face Spaces)
EXPOSE 7860

# Berpindah ke folder backend sebelum menjalankan server
WORKDIR /app/backend

# Menjalankan aplikasi menggunakan uvicorn di port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
