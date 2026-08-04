# Aturan Pengembangan Aplikasi

## A. Penambahan Fitur

1. Tambahkan fitur baru tanpa mengubah perilaku fitur yang sudah ada.
2. Jangan menghapus fungsi, komponen, file, atau variabel yang masih digunakan.
3. Jangan melakukan refactor besar kecuali benar-benar diperlukan.
4. Isolasi fitur baru ke dalam modul, komponen, atau file terpisah apabila memungkinkan.
5. Gunakan kembali fungsi yang sudah ada dan hindari duplikasi kode.
6. Pertahankan tampilan dan alur kerja aplikasi yang sudah berjalan.
7. Pastikan seluruh fitur lama tetap berfungsi setelah fitur baru ditambahkan.

## B. Perbaikan Bug

1. Perbaiki hanya bagian kode yang menjadi penyebab masalah (root cause).
2. Jangan mengubah logika fitur lain yang tidak berkaitan.
3. Jangan mengubah struktur proyek apabila tidak diperlukan.
4. Jangan menghapus fungsi yang masih digunakan oleh fitur lain.
5. Jangan mengganti nama fungsi, class, variabel, id, atau selector yang telah digunakan kecuali benar-benar diperlukan.
6. Pastikan perbaikan tidak menimbulkan bug baru (regression).
7. Jika terdapat beberapa cara untuk memperbaiki masalah, pilih solusi dengan perubahan kode paling kecil (minimal change).

## C. Sebelum Melakukan Perubahan

1. Analisis terlebih dahulu penyebab masalah.
2. Tentukan file yang benar-benar perlu diubah.
3. Jelaskan rencana perubahan secara singkat.
4. Hindari mengubah file yang tidak berkaitan.

## D. Setelah Perubahan

1. Pastikan seluruh fitur lama tetap berjalan.
2. Lakukan pengecekan terhadap fitur yang terdampak.
3. Pastikan tidak ada error baru.
4. Ringkas perubahan yang telah dilakukan.

## E. Struktur Kode

1. Hindari duplikasi kode.
2. Gunakan fungsi yang sudah ada jika memungkinkan.
3. Pisahkan logika ke helper/service apabila digunakan berulang.
4. Gunakan nama variabel dan fungsi yang konsisten.
5. Hindari hardcode.

## F. Aturan Pengembangan

- Jangan mengubah struktur proyek tanpa izin.
- Tambahkan fitur sebagai modul baru.
- Backend dan frontend harus dipisahkan.
- Daftarkan modul dan endpoint sesuai arsitektur proyek.
- Jangan menghapus, memindahkan, atau mengganti nama modul yang sudah digunakan.
- Gunakan kembali fungsi yang ada.
- Hindari duplikasi kode.
- Jangan menambah dependency tanpa persetujuan.
- Pertahankan kompatibilitas API dan database.
- Lakukan perubahan seminimal mungkin.

## G. Prioritas Validasi

Gunakan urutan berikut:

1. Rule-Based
2. Regex
3. Database
4. OCR
5. AI

Gunakan AI hanya apabila metode sebelumnya tidak dapat menyelesaikan pemeriksaan.

## H. Performa

1. Hindari request AI yang tidak diperlukan.
2. Gunakan cache apabila memungkinkan.
3. Hindari OCR berulang pada file yang sama.
4. Jangan memproses ulang data yang sudah tersedia.
5. Utamakan efisiensi waktu proses dan penggunaan token.

## I. Output

1. Berikan jawaban singkat dan jelas.
2. Fokus pada hasil dan perubahan.
3. Jangan mengubah fitur di luar ruang lingkup permintaan.
4. Jika terdapat potensi konflik dengan fitur lain, jelaskan terlebih dahulu sebelum melakukan perubahan.

---

## J. Prinsip Utama

- Minimal Change
- Backward Compatible
- Modular
- Reusable
- Efficient
- Maintainable
- Jangan melakukan perubahan yang tidak diminta.
  Jangan Langsung Upload Coding terbaru ke Github
