"""
vision.py — Modul Computer Vision Peta Batas Desa
===================================================
Deteksi visual komponen peta menggunakan OpenCV:
1. Arah Utara (north arrow / simbol kompas)
2. Skala Grafis (bar scale)
3. Inset Lokasi (peta mini di sudut)
4. Logo Instansi (deteksi kotak dengan konten gambar)
5. Batas Administrasi (deteksi garis tegas/batas)

Setiap fungsi mengembalikan:
{
  "detected": bool,
  "confidence": float (0.0 - 1.0),
  "bbox": (x, y, w, h) atau None,
  "evidence": str (deskripsi bukti)
}
"""

import logging
from typing import Dict, Tuple, Optional, Any, List

import numpy as np

logger = logging.getLogger("peta_audit.vision")


def _safe_cv_import():
    """Import cv2 dengan penanganan error."""
    try:
        import cv2
        return cv2
    except ImportError:
        logger.error("OpenCV (cv2) tidak tersedia. Pastikan opencv-python-headless terinstall.")
        return None


def detect_north_arrow(image_cv: np.ndarray) -> Dict[str, Any]:
    """
    Deteksi simbol arah utara (panah kompas / huruf N).
    Strategi:
    1. Cari wilayah yang mengandung bentuk panah runcing (triangular)
    2. Cari teks 'N' (Utara) dengan OCR regional
    3. Cari pola template sederhana di sudut-sudut peta

    North arrow biasanya ada di:
    - Pojok kanan atas body peta
    - Di dalam atau dekat legenda
    - Ukuran kecil (< 5% area gambar)
    """
    cv2 = _safe_cv_import()
    if cv2 is None:
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": "OpenCV tidak tersedia"}

    try:
        h, w = image_cv.shape[:2]

        # === Strategi 1: Template Matching dengan pola panah sederhana ===
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

        # Area pencarian: 60% kanan gambar (north arrow biasanya di kanan)
        search_region = gray[:, int(w * 0.40):]

        # Deteksi kontur tajam (segitiga/panah) menggunakan Canny + kontur
        edges = cv2.Canny(search_region, 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        arrow_candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            peri = cv2.arcLength(cnt, True)
            if peri == 0 or area < 100:
                continue

            # Cek circularity (panah cenderung memanjang)
            circularity = 4 * np.pi * area / (peri * peri)

            # Approximate ke polygon
            approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
            vertices = len(approx)

            # Panah biasanya 3-7 vertex, tidak terlalu circular
            if 3 <= vertices <= 8 and 0.1 < circularity < 0.7:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect = ch / cw if cw > 0 else 0
                # North arrow biasanya lebih tinggi dari lebar
                if 0.5 < aspect < 4.0 and 100 < area < w * h * 0.02:
                    arrow_candidates.append({
                        "x": x + int(w * 0.40),
                        "y": y,
                        "w": cw,
                        "h": ch,
                        "area": area,
                        "vertices": vertices
                    })

        if arrow_candidates:
            # Ambil kandidat terbesar
            best = max(arrow_candidates, key=lambda c: c["area"])
            return {
                "detected": True,
                "confidence": 0.65,
                "bbox": (best["x"], best["y"], best["w"], best["h"]),
                "evidence": f"Computer Vision mendeteksi bentuk panah ({best['vertices']} vertex) di area kanan peta. Luas: {int(best['area'])} px²"
            }

        # === Strategi 2: Deteksi huruf 'U' atau 'N' terisolasi (teks Utara) ===
        # Cari area dengan teks 'U' atau 'N' yang terisolasi di kuadran kanan
        # (ditangani di validator.py dengan OCR)

        return {
            "detected": False,
            "confidence": 0.15,
            "bbox": None,
            "evidence": "Tidak ada bentuk panah yang terdeteksi oleh Computer Vision"
        }

    except Exception as e:
        logger.error(f"detect_north_arrow error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}


def detect_scale_bar(image_cv: np.ndarray) -> Dict[str, Any]:
    """
    Deteksi skala grafis (bar scale / graphic scale).
    Skala grafis berupa batang kotak hitam-putih berselang dengan label jarak.
    
    Strategi:
    - Cari pola horizontal berselang-seling hitam/putih
    - Biasanya di bawah peta atau dekat legenda
    """
    cv2 = _safe_cv_import()
    if cv2 is None:
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": "OpenCV tidak tersedia"}

    try:
        h, w = image_cv.shape[:2]
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

        # Cari di 30% bawah gambar (skala grafis biasanya di bawah)
        bottom_region = gray[int(h * 0.65):, :]
        bh, bw = bottom_region.shape

        # Deteksi pola garis horizontal dengan biner
        _, binary = cv2.threshold(bottom_region, 128, 255, cv2.THRESH_BINARY)

        # Hitung alternating black-white blocks (karakteristik skala grafis)
        # Scan horizontal pada titik tengah vertikal
        for scan_y in range(int(bh * 0.1), int(bh * 0.9), max(1, bh // 10)):
            row = binary[scan_y, :]
            transitions = 0
            prev = row[0]
            run_starts = []
            current_start = 0

            for px_i in range(1, len(row)):
                if row[px_i] != prev:
                    transitions += 1
                    run_length = px_i - current_start
                    if run_length > 20:  # Hanya blok yang cukup lebar
                        run_starts.append(current_start)
                    current_start = px_i
                    prev = row[px_i]

            # Skala grafis biasanya punya 4-12 transisi dengan blok berukuran hampir sama
            if 4 <= transitions <= 20:
                # Estimasi posisi skala grafis
                return {
                    "detected": True,
                    "confidence": 0.60,
                    "bbox": (0, int(h * 0.65) + scan_y - 10, w, 40),
                    "evidence": f"Computer Vision mendeteksi pola alternating hitam-putih horizontal ({transitions} transisi) di area bawah peta — karakteristik skala grafis"
                }

        # === Fallback: Deteksi kotak tipis horizontal ===
        edges = cv2.Canny(gray[int(h * 0.60):, :], 30, 100)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=int(w * 0.10),
                                minLineLength=int(w * 0.05), maxLineGap=10)

        if lines is not None:
            long_h_lines = [l for l in lines if abs(l[0][3] - l[0][1]) < 5 and (l[0][2] - l[0][0]) > w * 0.05]
            if len(long_h_lines) >= 2:
                return {
                    "detected": True,
                    "confidence": 0.45,
                    "bbox": None,
                    "evidence": f"Terdeteksi {len(long_h_lines)} garis horizontal panjang di area bawah — kemungkinan skala grafis"
                }

        return {
            "detected": False,
            "confidence": 0.1,
            "bbox": None,
            "evidence": "Pola skala grafis tidak terdeteksi oleh Computer Vision"
        }

    except Exception as e:
        logger.error(f"detect_scale_bar error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}


def detect_inset_map(image_cv: np.ndarray) -> Dict[str, Any]:
    """
    Deteksi inset lokasi (peta mini di sudut).
    Inset biasanya berupa kotak kecil berisi peta dengan warna kontras
    (biasanya merah atau warna berbeda dari peta utama) di salah satu sudut.
    """
    cv2 = _safe_cv_import()
    if cv2 is None:
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": "OpenCV tidak tersedia"}

    try:
        h, w = image_cv.shape[:2]

        # Definisikan 4 pojok untuk pencarian
        corners = {
            "kiri_bawah":   (0, int(h * 0.65), int(w * 0.28), int(h * 0.35)),
            "kanan_bawah":  (int(w * 0.72), int(h * 0.65), int(w * 0.28), int(h * 0.35)),
            "kiri_atas":    (0, 0, int(w * 0.25), int(h * 0.28)),
            "kanan_atas":   (int(w * 0.72), 0, int(w * 0.28), int(h * 0.28)),
        }

        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

        for corner_name, (cx, cy, cw, ch) in corners.items():
            region = image_cv[cy:cy+ch, cx:cx+cw]
            if region.size == 0:
                continue

            region_gray = gray[cy:cy+ch, cx:cx+cw]

            # Cari kotak/border di dalam region
            edges = cv2.Canny(region_gray, 40, 120)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Cari kontur yang mendekati persegi panjang
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < (cw * ch * 0.05):  # Minimal 5% area pojok
                    continue

                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)

                if 4 <= len(approx) <= 8:
                    # Cek ada warna merah (tanda batas wilayah pada inset)
                    x_cnt, y_cnt, w_cnt, h_cnt = cv2.boundingRect(cnt)
                    sub = region[y_cnt:y_cnt+h_cnt, x_cnt:x_cnt+w_cnt]
                    if sub.size > 0:
                        # Deteksi kanal merah dominan
                        r_mean = np.mean(sub[:, :, 2])
                        g_mean = np.mean(sub[:, :, 1])
                        b_mean = np.mean(sub[:, :, 0])

                        if r_mean > 100 and r_mean > g_mean * 1.3 and r_mean > b_mean * 1.3:
                            return {
                                "detected": True,
                                "confidence": 0.70,
                                "bbox": (cx + x_cnt, cy + y_cnt, w_cnt, h_cnt),
                                "evidence": f"Computer Vision mendeteksi kotak dengan warna merah signifikan di pojok {corner_name} — karakteristik inset lokasi"
                            }

                    # Meskipun tanpa warna merah, kotak di pojok = kandidat inset
                    if area > cw * ch * 0.12:
                        return {
                            "detected": True,
                            "confidence": 0.45,
                            "bbox": (cx + x_cnt, cy + y_cnt, w_cnt, h_cnt),
                            "evidence": f"Computer Vision mendeteksi kotak signifikan di pojok {corner_name} — kemungkinan inset lokasi"
                        }

        return {
            "detected": False,
            "confidence": 0.10,
            "bbox": None,
            "evidence": "Tidak ada kotak inset yang terdeteksi di keempat pojok peta"
        }

    except Exception as e:
        logger.error(f"detect_inset_map error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}


def detect_logo(image_cv: np.ndarray) -> Dict[str, Any]:
    """
    Deteksi logo instansi.
    Logo biasanya:
    - Di pojok atas (kiri atau kanan)
    - Berbentuk lingkaran atau persegi dengan warna kompleks
    - Ukuran kecil-sedang
    """
    cv2 = _safe_cv_import()
    if cv2 is None:
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": "OpenCV tidak tersedia"}

    try:
        h, w = image_cv.shape[:2]

        # Cari di 25% atas gambar, pojok kiri dan kanan
        logo_zones = [
            (0, 0, int(w * 0.20), int(h * 0.18)),            # Kiri atas
            (int(w * 0.80), 0, int(w * 0.20), int(h * 0.18)), # Kanan atas
        ]

        for (lx, ly, lw, lh) in logo_zones:
            region = image_cv[ly:ly+lh, lx:lx+lw]
            if region.size == 0:
                continue

            # Hitung kompleksitas warna (logo biasanya memiliki banyak warna berbeda)
            unique_colors = len(np.unique(region.reshape(-1, 3), axis=0))
            pixel_count = lw * lh

            color_density = unique_colors / pixel_count if pixel_count > 0 else 0

            # Logo cenderung memiliki variasi warna tinggi
            if color_density > 0.15 and unique_colors > 200:
                # Cari lingkaran (logo sering berbentuk circular)
                gray_logo = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                circles = cv2.HoughCircles(
                    gray_logo, cv2.HOUGH_GRADIENT, dp=1.2,
                    minDist=int(min(lw, lh) * 0.3),
                    param1=50, param2=30,
                    minRadius=int(min(lw, lh) * 0.1),
                    maxRadius=int(min(lw, lh) * 0.5)
                )
                if circles is not None:
                    cx_c, cy_c, r = circles[0][0]
                    return {
                        "detected": True,
                        "confidence": 0.65,
                        "bbox": (lx, ly, lw, lh),
                        "evidence": f"Computer Vision mendeteksi elemen berbentuk lingkaran dengan kompleksitas warna tinggi di pojok atas — kemungkinan logo instansi"
                    }

                # Meskipun tanpa lingkaran, warna kompleks di pojok = kandidat logo
                return {
                    "detected": True,
                    "confidence": 0.40,
                    "bbox": (lx, ly, lw, lh),
                    "evidence": f"Computer Vision mendeteksi region dengan variasi warna tinggi ({unique_colors} warna unik) di pojok atas — kemungkinan logo instansi"
                }

        return {
            "detected": False,
            "confidence": 0.10,
            "bbox": None,
            "evidence": "Tidak ada elemen logo yang terdeteksi di area pojok atas"
        }

    except Exception as e:
        logger.error(f"detect_logo error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}


def detect_boundary_lines(image_cv: np.ndarray) -> Dict[str, Any]:
    """
    Deteksi keberadaan batas administrasi.
    Batas administrasi pada peta biasanya berupa:
    - Garis tegas berwarna tertentu (merah, ungu, hitam tebal)
    - Garis putus-putus
    - Lebih panjang dan berkesinambungan dari garis grid
    """
    cv2 = _safe_cv_import()
    if cv2 is None:
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": "OpenCV tidak tersedia"}

    try:
        h, w = image_cv.shape[:2]

        # Deteksi garis merah/ungu (warna batas administrasi umum)
        hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)

        # Merah: dua range HSV
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        mask_r1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_r2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_red = cv2.bitwise_or(mask_r1, mask_r2)

        # Ungu/magenta
        lower_purple = np.array([130, 50, 50])
        upper_purple = np.array([160, 255, 255])
        mask_purple = cv2.inRange(hsv, lower_purple, upper_purple)

        # Hitam tebal
        lower_black = np.array([0, 0, 0])
        upper_black = np.array([180, 60, 60])
        mask_black = cv2.inRange(hsv, lower_black, upper_black)

        # Gabungkan semua mask batas
        mask_boundary = cv2.bitwise_or(mask_red, cv2.bitwise_or(mask_purple, mask_black))

        # Hitung piksel batas
        boundary_pixels = cv2.countNonZero(mask_boundary)
        total_pixels = w * h
        boundary_ratio = boundary_pixels / total_pixels

        # Cek apakah ada garis panjang berwarna batas
        edges_on_mask = cv2.Canny(mask_boundary, 30, 100)
        lines = cv2.HoughLinesP(edges_on_mask, 1, np.pi / 180,
                                threshold=int(min(w, h) * 0.1),
                                minLineLength=int(min(w, h) * 0.08),
                                maxLineGap=20)

        n_lines = len(lines) if lines is not None else 0

        if boundary_ratio > 0.005 and n_lines >= 3:
            return {
                "detected": True,
                "confidence": min(0.85, 0.5 + boundary_ratio * 10 + n_lines * 0.02),
                "bbox": None,
                "evidence": f"Computer Vision mendeteksi {n_lines} garis batas berwarna (merah/ungu/hitam) — karakteristik batas administrasi. Rasio piksel batas: {boundary_ratio:.3%}"
            }
        elif n_lines >= 2:
            return {
                "detected": True,
                "confidence": 0.40,
                "bbox": None,
                "evidence": f"Terdeteksi {n_lines} garis berwarna yang kemungkinan merupakan batas administrasi"
            }

        return {
            "detected": False,
            "confidence": 0.15,
            "bbox": None,
            "evidence": f"Garis batas administrasi tidak terdeteksi secara jelas (hanya {n_lines} garis kandidat)"
        }

    except Exception as e:
        logger.error(f"detect_boundary_lines error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}


def detect_legend_visually(image_cv: np.ndarray) -> Dict[str, Any]:
    """
    Deteksi legenda secara visual:
    - Cari area dengan deretan simbol kecil berjajar vertikal
    - Biasanya terdapat di panel kanan atau bawah
    - Pola: simbol (kotak/garis berwarna) + teks di sebelah kanan
    """
    cv2 = _safe_cv_import()
    if cv2 is None:
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": "OpenCV tidak tersedia"}

    try:
        h, w = image_cv.shape[:2]

        # Fokus area kanan (60-100%) dan bawah (40-100%)
        search_x = int(w * 0.55)
        search_region = image_cv[:, search_x:]
        sh, sw = search_region.shape[:2]

        gray = cv2.cvtColor(search_region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 30, 100)

        # Cari kotak-kotak kecil berjejer (simbol legenda)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        small_boxes = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            aspect = bw / bh if bh > 0 else 0

            # Simbol legenda: kotak kecil hampir persegi
            if (50 < area < (sw * sh * 0.005)) and (0.3 < aspect < 3.0):
                small_boxes.append({"x": x + search_x, "y": y, "w": bw, "h": bh})

        # Jika ada banyak kotak kecil berjejer, kemungkinan itu legenda
        if len(small_boxes) >= 4:
            ys = [b["y"] for b in small_boxes]
            ys.sort()
            # Cek apakah berjejer vertikal (y meningkat secara reguler)
            vertical_spread = max(ys) - min(ys) if ys else 0

            if vertical_spread > sh * 0.10:
                x_pos = search_x
                y_pos = min(ys)
                leg_h = vertical_spread + 40

                return {
                    "detected": True,
                    "confidence": min(0.75, 0.4 + len(small_boxes) * 0.05),
                    "bbox": (x_pos, y_pos, sw, leg_h),
                    "evidence": f"Computer Vision mendeteksi {len(small_boxes)} simbol kecil berjejer vertikal di panel kanan — karakteristik legenda peta"
                }

        return {
            "detected": False,
            "confidence": 0.15,
            "bbox": None,
            "evidence": "Pola simbol legenda tidak terdeteksi di area kanan peta"
        }

    except Exception as e:
        logger.error(f"detect_legend_visually error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}
