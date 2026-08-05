"""
ocr.py — Modul OCR Peta Batas Desa
====================================
Wrapper pytesseract untuk:
- Ekstraksi teks penuh dari gambar peta
- Ekstraksi teks per-region (bounding box)
- Konfigurasi optimal untuk dokumen peta BIG (bahasa Indonesia + Inggris)
- Preprocessing gambar sebelum OCR (grayscale, threshold, denoise)
"""

import logging
import re
from typing import List, Tuple, Dict, Any, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger("peta_audit.ocr")

# Konfigurasi Tesseract untuk peta BIG (mode page segmentation = 1: auto OSD)
# PSM 3 = Fully automatic page segmentation (recommended untuk peta)
# PSM 6 = Assume a single uniform block of text (untuk region kecil)
TESS_CONFIG_FULL = "--oem 3 --psm 3"
TESS_CONFIG_BLOCK = "--oem 3 --psm 6"
TESS_CONFIG_LINE  = "--oem 3 --psm 7"
TESS_LANG = "ind+eng"  # Bahasa Indonesia + Inggris

_tesseract_available = None
_tesseract_lang_available = None


def _check_tesseract() -> Tuple[bool, bool]:
    """Cek ketersediaan Tesseract dan bahasa Indonesia."""
    global _tesseract_available, _tesseract_lang_available
    if _tesseract_available is not None:
        return _tesseract_available, _tesseract_lang_available

    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        _tesseract_available = True
        logger.info("Tesseract OCR tersedia.")
    except Exception as e:
        _tesseract_available = False
        _tesseract_lang_available = False
        logger.warning(f"Tesseract tidak tersedia: {e}. OCR akan dilewati.")
        return False, False

    try:
        import pytesseract
        langs = pytesseract.get_languages()
        _tesseract_lang_available = "ind" in langs
        if _tesseract_lang_available:
            logger.info("Data bahasa 'ind' tersedia untuk Tesseract.")
        else:
            logger.warning("Data bahasa 'ind' tidak tersedia. Menggunakan 'eng' saja.")
    except Exception:
        _tesseract_lang_available = False

    return _tesseract_available, _tesseract_lang_available


def _preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """
    Preprocessing gambar sebelum OCR:
    1. Konversi ke grayscale
    2. Adaptive threshold (OTSU)
    3. Denoise ringan
    """
    try:
        import cv2
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Gaussian blur ringan untuk mengurangi noise
        blur = cv2.GaussianBlur(gray, (1, 1), 0)
        # OTSU threshold untuk binarisasi adaptif
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh
    except Exception as e:
        logger.warning(f"Preprocessing OCR gagal: {e}")
        return image


def extract_full_text(
    image_pil: Image.Image,
    image_cv: np.ndarray,
    raw_text_from_pdf: str = ""
) -> str:
    """
    Ekstraksi teks penuh dari gambar peta.
    Prioritas:
    1. raw_text_from_pdf (teks vektor PDF — paling akurat)
    2. pytesseract OCR pada gambar

    Mengembalikan string teks gabungan.
    """
    # Jika raw_text dari PDF sudah cukup panjang, gunakan itu sebagai prioritas
    if raw_text_from_pdf and len(raw_text_from_pdf.strip()) > 100:
        logger.info(f"Menggunakan teks vektor PDF ({len(raw_text_from_pdf)} karakter) sebagai sumber utama.")
        ocr_text = _run_ocr_on_image(image_pil, image_cv)
        # Gabungkan keduanya agar tidak ada yang terlewat
        combined = raw_text_from_pdf + "\n\n[OCR SUPPLEMENT]\n" + ocr_text
        return combined

    # Jika tidak ada teks vektor, jalankan OCR
    ocr_text = _run_ocr_on_image(image_pil, image_cv)
    return ocr_text


def _run_ocr_on_image(image_pil: Image.Image, image_cv: np.ndarray) -> str:
    """Jalankan pytesseract pada gambar."""
    tess_ok, lang_ok = _check_tesseract()
    if not tess_ok:
        logger.warning("Tesseract tidak tersedia. Mengembalikan teks kosong.")
        return ""

    try:
        import pytesseract
        lang = TESS_LANG if lang_ok else "eng"

        # Preprocess
        preprocessed = _preprocess_for_ocr(image_cv)
        pil_preprocessed = Image.fromarray(preprocessed)

        text = pytesseract.image_to_string(pil_preprocessed, lang=lang, config=TESS_CONFIG_FULL)
        logger.info(f"OCR selesai: {len(text)} karakter diekstrak.")
        return text
    except Exception as e:
        logger.error(f"OCR gagal: {e}")
        return ""


def extract_text_regions(
    image_pil: Image.Image,
    image_cv: np.ndarray
) -> List[Dict[str, Any]]:
    """
    Ekstraksi teks dengan bounding box per kata/blok.
    Mengembalikan list of:
      { 'text': str, 'left': int, 'top': int, 'width': int, 'height': int, 'conf': float }
    """
    tess_ok, lang_ok = _check_tesseract()
    if not tess_ok:
        return []

    try:
        import pytesseract
        lang = TESS_LANG if lang_ok else "eng"

        preprocessed = _preprocess_for_ocr(image_cv)
        pil_preprocessed = Image.fromarray(preprocessed)

        data = pytesseract.image_to_data(
            pil_preprocessed,
            lang=lang,
            config=TESS_CONFIG_FULL,
            output_type=pytesseract.Output.DICT
        )

        regions = []
        n_boxes = len(data.get("text", []))
        for i in range(n_boxes):
            word = data["text"][i].strip()
            conf = float(data["conf"][i]) if data["conf"][i] != -1 else 0.0
            if word and conf > 30:  # Filter low-confidence noise
                regions.append({
                    "text": word,
                    "left": data["left"][i],
                    "top": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                    "conf": conf
                })

        logger.info(f"extract_text_regions: {len(regions)} region kata diekstrak.")
        return regions

    except Exception as e:
        logger.error(f"extract_text_regions gagal: {e}")
        return []


def extract_region_text(
    image_cv: np.ndarray,
    x: int, y: int, w: int, h: int,
    config: str = TESS_CONFIG_BLOCK
) -> str:
    """
    Ekstrak teks dari sub-region (crop) gambar.
    Berguna untuk memeriksa area spesifik (judul, legenda, dll).
    """
    tess_ok, lang_ok = _check_tesseract()
    if not tess_ok:
        return ""

    try:
        import pytesseract
        lang = TESS_LANG if lang_ok else "eng"

        crop = image_cv[y:y+h, x:x+w]
        if crop.size == 0:
            return ""

        preprocessed = _preprocess_for_ocr(crop)
        pil_crop = Image.fromarray(preprocessed)

        text = pytesseract.image_to_string(pil_crop, lang=lang, config=config)
        return text.strip()
    except Exception as e:
        logger.warning(f"extract_region_text gagal di ({x},{y},{w},{h}): {e}")
        return ""
