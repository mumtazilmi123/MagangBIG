"""
layout.py — Modul Deteksi Layout/Region Peta Batas Desa
=========================================================
Mendeteksi dan melokalisasi region-region utama pada peta:
- Area judul (biasanya di atas)
- Area legenda (biasanya di pojok kanan bawah atau kanan)
- Area inset (peta mini, biasanya di sudut)
- Area informasi peta (di bawah: proyeksi, datum, sumber)
- Area utama peta (body peta)

Pendekatan:
- Analisis distribusi warna dan garis tepi
- Deteksi kotak/border dengan OpenCV
- Segmentasi berdasarkan posisi heuristik (rule-based layout)
"""

import logging
from typing import Dict, Tuple, Optional, Any, List

import numpy as np

logger = logging.getLogger("peta_audit.layout")


def _get_image_dimensions(image_cv: np.ndarray) -> Tuple[int, int]:
    """Kembalikan (height, width) gambar."""
    h, w = image_cv.shape[:2]
    return h, w


def detect_regions_heuristic(image_cv: np.ndarray) -> Dict[str, Dict]:
    """
    Deteksi region berdasarkan heuristik posisi layout peta BIG standar:
    - Judul: 10% teratas
    - Legenda: pojok kanan bawah (20% lebar × 25% tinggi)
    - Inset: pojok kiri bawah atau kanan atas (15% × 20%)
    - Info bawah: 15% terbawah
    - Body peta: area tengah-besar

    Mengembalikan dict {region_name: {x, y, w, h}}
    """
    h, w = _get_image_dimensions(image_cv)

    regions = {
        "title":  {"x": 0, "y": 0, "w": w, "h": int(h * 0.12)},
        "top_info": {"x": 0, "y": 0, "w": w, "h": int(h * 0.20)},
        "bottom_info": {"x": 0, "y": int(h * 0.82), "w": w, "h": int(h * 0.18)},
        "right_panel": {"x": int(w * 0.75), "y": 0, "w": int(w * 0.25), "h": h},
        "left_panel": {"x": 0, "y": 0, "w": int(w * 0.20), "h": h},
        "legend_area": {"x": int(w * 0.72), "y": int(h * 0.35), "w": int(w * 0.28), "h": int(h * 0.55)},
        "inset_bl": {"x": 0, "y": int(h * 0.70), "w": int(w * 0.25), "h": int(h * 0.30)},
        "inset_tr": {"x": int(w * 0.75), "y": 0, "w": int(w * 0.25), "h": int(h * 0.25)},
        "map_body": {"x": int(w * 0.05), "y": int(h * 0.12), "w": int(w * 0.68), "h": int(h * 0.70)},
        "full": {"x": 0, "y": 0, "w": w, "h": h},
    }
    return regions


def detect_border_boxes(image_cv: np.ndarray) -> List[Dict]:
    """
    Deteksi kotak/bingkai pada peta menggunakan OpenCV contour detection.
    Mengembalikan list of { x, y, w, h, area } yang sudah difilter
    (hanya kotak signifikan dengan area > 1% gambar).
    """
    try:
        import cv2
        h, w = _get_image_dimensions(image_cv)
        min_area = w * h * 0.01  # Minimum 1% area gambar

        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # Dilasi ringan untuk menyambungkan garis putus
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            if area > min_area:
                # Filter kotak yang terlalu besar (>80% gambar = gambar keseluruhan)
                if area < w * h * 0.80:
                    boxes.append({"x": x, "y": y, "w": bw, "h": bh, "area": area})

        # Urutkan dari terbesar ke terkecil
        boxes.sort(key=lambda b: b["area"], reverse=True)
        logger.info(f"detect_border_boxes: {len(boxes)} kotak terdeteksi.")
        return boxes[:20]  # Ambil 20 terbesar

    except Exception as e:
        logger.warning(f"detect_border_boxes gagal: {e}")
        return []


def find_legend_region(image_cv: np.ndarray, boxes: List[Dict]) -> Optional[Dict]:
    """
    Coba temukan region legenda dari daftar kotak yang terdeteksi.
    Legenda biasanya:
    - Berada di sebelah kanan atau bawah
    - Memiliki rasio yang cukup (lebih tinggi dari lebar atau persegi)
    - Berisi banyak teks pendek dengan simbol
    """
    h, w = _get_image_dimensions(image_cv)

    # Cari kotak yang berada di 40% kanan gambar
    right_boxes = [b for b in boxes if b["x"] > w * 0.50]
    if right_boxes:
        # Ambil kotak terbesar di area kanan
        return right_boxes[0]

    # Fallback: cari di area bawah
    bottom_boxes = [b for b in boxes if b["y"] > h * 0.55]
    if bottom_boxes:
        return bottom_boxes[0]

    return None


def find_inset_region(image_cv: np.ndarray, boxes: List[Dict]) -> Optional[Dict]:
    """
    Coba temukan region inset lokasi.
    Inset biasanya:
    - Kotak kecil (< 20% area gambar)
    - Berisi peta mini dengan warna kontras (merah/garis)
    - Di sudut gambar (pojok kiri atas, kanan atas, kiri bawah, kanan bawah)
    """
    h, w = _get_image_dimensions(image_cv)
    max_inset_area = w * h * 0.15

    corner_boxes = []
    for b in boxes:
        if b["area"] < max_inset_area:
            # Cek apakah berada di pojok
            in_left = b["x"] < w * 0.25
            in_right = (b["x"] + b["w"]) > w * 0.75
            in_top = b["y"] < h * 0.25
            in_bottom = (b["y"] + b["h"]) > h * 0.75

            if (in_left or in_right) and (in_top or in_bottom):
                corner_boxes.append(b)

    if corner_boxes:
        return corner_boxes[0]
    return None


def analyze_grid_presence(image_cv: np.ndarray) -> Dict[str, Any]:
    """
    Deteksi keberadaan grid koordinat pada peta menggunakan analisis garis Hough & perpotongan.
    Delegasi ke modul vision.analyze_grid_presence.
    """
    try:
        from peta_audit.modules.vision import analyze_grid_presence as v_grid
        return v_grid(image_cv)
    except Exception as e:
        logger.warning(f"analyze_grid_presence gagal: {e}")
        return {"has_grid": False, "confidence": 0.0, "h_lines": 0, "v_lines": 0, "evidence": str(e)}
