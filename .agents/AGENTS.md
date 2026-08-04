# Aturan Pengembangan Aplikasi

## A. Penambahan Fitur

1. Tambahkan fitur baru tanpa mengubah perilaku fitur yang sudah ada.
2. Jangan menghapus fungsi, komponen, file, atau variabel yang masih digunakan.
3. Jangan melakukan refactor besar kecuali benar-benar diperlukan.
4. Isolasi fitur baru ke dalam modul, komponen, atau file terpisah apabila memungkinkan.
5. Gunakan kembali fungsi yang sudah ada dan hindari duplikasi kode.
6. Pertahankan tampilan dan alur kerja aplikasi yang sudah berjalan.
7. Pastikan seluruh fitur lama tetap berfungsi setelah fitur baru ditambahkan.

---

## B. Perbaikan Bug

1. Perbaiki hanya bagian kode yang menjadi penyebab masalah (root cause).
2. Jangan mengubah logika fitur lain yang tidak berkaitan.
3. Jangan mengubah struktur proyek apabila tidak diperlukan.
4. Jangan menghapus fungsi yang masih digunakan oleh fitur lain.
5. Jangan mengganti nama fungsi, class, variabel, id, atau selector yang telah digunakan kecuali benar-benar diperlukan.
6. Pastikan perbaikan tidak menimbulkan bug baru (regression).
7. Jika terdapat beberapa cara untuk memperbaiki masalah, pilih solusi dengan perubahan kode paling kecil (minimal change).
