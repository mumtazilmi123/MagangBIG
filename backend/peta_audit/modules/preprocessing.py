"""
preprocessing.py — Modul Preprocessing Peta Batas Desa
=======================================================
Fungsi:
- Konversi file PDF/JPG/PNG/TIFF ke numpy array (BGR, untuk OpenCV)
- Untuk PDF: ekstrak halaman pertama (peta utama) sebagai gambar
- Normalisasi ukuran untuk keterbacaan OCR dan Computer Vision
- Menghasilkan:
    * image_cv   : numpy array BGR (untuk OpenCV)
    * image_pil  : PIL Image RGB (untuk pytesseract)
    * full_text  : teks mentah dari pdfplumber jika file PDF
"""

import os
import io
import logging
from typing import Tuple, Optional, Dict, Any

import numpy as np
from PIL import Image

logger = logging.getLogger("peta_audit.preprocessing")

# Resolusi render PDF (DPI). Lebih tinggi = lebih akurat OCR, lebih lambat.
PDF_RENDER_DPI = 200

# Ukuran gambar output untuk OCR (lebar maksimum dalam piksel)
OCR_MAX_WIDTH = 4000


def _pdf_to_pil(file_bytes: bytes, page_index: int = 0) -> Tuple[Optional[Image.Image], str]:
    """
    Render halaman PDF menjadi PIL Image.
    Prioritas: pdf2image (Poppler) → pypdf + Pillow fallback.
    Mengembalikan (pil_image, raw_text_from_pdfplumber).
    """
    raw_text = ""

    # Ekstrak teks vektor dari PDF dengan pdfplumber (lebih akurat dari OCR untuk PDF digital)
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if page_index < len(pdf.pages):
                page = pdf.pages[page_index]
                raw_text = page.extract_text() or ""
                logger.info(f"pdfplumber berhasil membaca {len(raw_text)} karakter teks vektor.")
    except Exception as e:
        logger.warning(f"pdfplumber gagal: {e}")

    # Coba render visual PDF ke gambar
    pil_image = None

    # Metode 1: pdf2image (butuh Poppler)
    try:
        from pdf2image import convert_from_bytes
        pages = convert_from_bytes(file_bytes, dpi=PDF_RENDER_DPI, first_page=page_index + 1, last_page=page_index + 1)
        if pages:
            pil_image = pages[0]
            logger.info(f"pdf2image berhasil render halaman {page_index + 1}: {pil_image.size}")
            return pil_image, raw_text
    except ImportError:
        logger.warning("pdf2image tidak tersedia. Coba pypdf fallback.")
    except Exception as e:
        logger.warning(f"pdf2image gagal: {e}. Coba pypdf fallback.")

    # Metode 2: pypdf — ekstrak gambar embed di dalam PDF
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        if page_index < len(reader.pages):
            page = reader.pages[page_index]
            images = list(page.images)
            if images:
                img_data = images[0].data
                pil_image = Image.open(io.BytesIO(img_data)).convert("RGB")
                logger.info(f"pypdf embed image berhasil: {pil_image.size}")
                return pil_image, raw_text
    except Exception as e:
        logger.warning(f"pypdf image extract gagal: {e}")

    # Jika semua gagal, kembalikan None
    logger.error("Semua metode render PDF gagal. File mungkin tidak memiliki konten gambar.")
    return None, raw_text


def _normalize_image(pil_image: Image.Image) -> Image.Image:
    """
    Normalisasi ukuran gambar agar tidak terlalu kecil atau terlalu besar.
    Menjaga aspek rasio.
    """
    w, h = pil_image.size
    if w > OCR_MAX_WIDTH:
        ratio = OCR_MAX_WIDTH / w
        new_w = OCR_MAX_WIDTH
        new_h = int(h * ratio)
        pil_image = pil_image.resize((new_w, new_h), Image.LANCZOS)
        logger.info(f"Gambar di-resize dari {w}x{h} menjadi {new_w}x{new_h}")
    elif w < 1000:
        # Upscale jika terlalu kecil agar OCR lebih akurat
        ratio = 1500 / w
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        pil_image = pil_image.resize((new_w, new_h), Image.LANCZOS)
        logger.info(f"Gambar di-upscale dari {w}x{h} menjadi {new_w}x{new_h}")
    return pil_image


def load_image_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Entry point utama. Menerima bytes file dan nama file.
    Mengembalikan dict berisi:
      - image_pil  : PIL Image RGB
      - image_cv   : numpy array BGR (OpenCV)
      - raw_text   : teks vektor dari PDF (jika tersedia)
      - page_count : jumlah halaman (untuk PDF)
      - error      : pesan error (jika gagal)
    """
    ext = os.path.splitext(filename.lower())[1]
    raw_text = ""
    page_count = 1

    try:
        if ext == ".pdf":
            pil_image, raw_text = _pdf_to_pil(file_bytes, page_index=0)
            # Hitung jumlah halaman
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                page_count = len(reader.pages)
            except Exception:
                page_count = 1

            if pil_image is None:
                # Tidak bisa render visual PDF, tapi masih bisa pakai raw_text
                logger.warning("Gambar PDF tidak bisa dirender. Hanya menggunakan teks vektor.")
                # Buat gambar blank sebagai placeholder
                pil_image = Image.new("RGB", (2000, 1414), color=(240, 240, 240))

        elif ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif"):
            pil_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            logger.info(f"Gambar {ext} dibuka: {pil_image.size}")
        else:
            return {
                "image_pil": None,
                "image_cv": None,
                "raw_text": "",
                "page_count": 0,
                "error": f"Format file tidak didukung: {ext}"
            }

        # Normalisasi ukuran
        pil_image = _normalize_image(pil_image)

        # Konversi ke OpenCV BGR
        image_cv = np.array(pil_image)
        image_cv = image_cv[:, :, ::-1].copy()  # RGB → BGR

        return {
            "image_pil": pil_image,
            "image_cv": image_cv,
            "raw_text": raw_text,
            "page_count": page_count,
            "error": None
        }

    except Exception as e:
        logger.error(f"Error saat memuat file {filename}: {e}")
        return {
            "image_pil": None,
            "image_cv": None,
            "raw_text": "",
            "page_count": 0,
            "error": str(e)
        }
