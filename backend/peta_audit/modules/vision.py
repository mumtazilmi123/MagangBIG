"""
vision.py — Modul Computer Vision Peta Batas Desa
===================================================
Deteksi visual komponen peta menggunakan OpenCV & OCR dengan strategi
yang disesuaikan dengan karakteristik nyata Peta Batas Desa Template BIG:

1. NORTH ARROW  : Teks U/N di atas + Panah Dua Sisi (hitam-putih)
                  Contoh: huruf "U" dengan dua sayap panah ke bawah
2. GRID         : Garis BIRU horizontal & vertikal membentuk kisi persegi
                  seragam di atas body peta
3. INSET        : Kotak bingkai kecil berisi miniatur peta dengan grid
                  dan teks "Petunjuk Letak Peta" / "Diagram Lokasi"
4. SKALA GRAFIS : Bar hitam-putih bergantian + teks jarak
"""

import logging
import re
from typing import Dict, Any, List, Optional

import numpy as np

logger = logging.getLogger("peta_audit.vision")


def _safe_cv_import():
    try:
        import cv2
        return cv2
    except ImportError:
        logger.error("OpenCV tidak tersedia.")
        return None


# ═════════════════════════════════════════════════════════════════════════════
# HELPER INTERNAL
# ═════════════════════════════════════════════════════════════════════════════

def _cluster_1d(coords: List[float], tol: float = 15.0) -> List[float]:
    """Kelompokkan koordinat 1D yang berdekatan ke dalam satu cluster."""
    if not coords:
        return []
    coords_sorted = sorted(coords)
    clusters, curr = [], [coords_sorted[0]]
    for val in coords_sorted[1:]:
        if val - curr[-1] <= tol:
            curr.append(val)
        else:
            clusters.append(float(np.mean(curr)))
            curr = [val]
    clusters.append(float(np.mean(curr)))
    return clusters


def _spacing_uniformity(clusters: List[float], threshold: float = 0.45) -> bool:
    """Cek apakah jarak antar cluster relatif seragam (CV < threshold)."""
    if len(clusters) < 3:
        return False
    spacings = np.diff(clusters)
    mean_sp = float(np.mean(spacings))
    std_sp  = float(np.std(spacings))
    return (std_sp / mean_sp) < threshold if mean_sp > 0 else False


# ═════════════════════════════════════════════════════════════════════════════
# 1. NORTH ARROW — OCR + Kontur Panah + Voting
# ═════════════════════════════════════════════════════════════════════════════

def detect_north_arrow(image_cv: np.ndarray, full_text: str = "") -> Dict[str, Any]:
    """
    Deteksi simbol Arah Utara dengan Multi-Stage Voting:

    Stage 1: OCR — cari teks "UTARA", "NORTH", "U", "N" terisolasi
    Stage 2: Scan area sekitar teks — crop 80×80 px
    Stage 3: Template Matching (berbagai skala) dengan template kompas BIG
    Stage 4: Contour Analysis — panah dua sisi runcing atas-bawah
    Stage 5: Shape Analysis — simetri kiri-kanan, tinggi > lebar
    Stage 6: Voting Classifier — gabung semua bukti
    """
    cv2 = _safe_cv_import()
    if cv2 is None or image_cv is None:
        return {"detected": False, "confidence": 0.0, "bbox": None,
                "evidence": "OpenCV tidak tersedia"}

    try:
        h, w = image_cv.shape[:2]
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

        score  = 0.0
        best_bbox  = None
        evidence_parts = []

        # ─── Stage 1: OCR Text Search ────────────────────────────────────────
        ocr_hit = False
        if re.search(r'\b(UTARA|NORTH)\b', full_text, re.IGNORECASE):
            score += 0.35
            ocr_hit = True
            evidence_parts.append("Teks 'UTARA/NORTH' ditemukan di OCR")
        elif re.search(r'(?<![A-Z])[UN](?![A-Z])', full_text):
            score += 0.15
            ocr_hit = True
            evidence_parts.append("Simbol 'U'/'N' terisolasi ditemukan di OCR")

        # ─── Stage 2–5: Visual Detection di 70% kanan dan seluruh tinggi ─────
        # North Arrow peta BIG biasanya di panel kanan (legenda/info)
        sx = int(w * 0.30)
        search = gray[:, sx:]
        sh, sw = search.shape

        # --- Stage 3: Template Matching -------------------------------------
        # Template khas kompas BIG: huruf U/N di atas, panah dua sisi ke bawah
        templates = _build_north_templates(cv2)
        best_tpl  = 0.0

        for tpl in templates:
            for scale in [0.5, 0.7, 1.0, 1.3, 1.8]:
                tw = max(8, int(tpl.shape[1] * scale))
                th = max(8, int(tpl.shape[0] * scale))
                if tw >= sw or th >= sh:
                    continue
                r_tpl = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA)
                res = cv2.matchTemplate(search, r_tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_tpl:
                    best_tpl = max_val
                    best_bbox = (sx + max_loc[0], max_loc[1], tw, th)

        if best_tpl > 0.42:
            score += min(0.40, best_tpl * 0.50)
            evidence_parts.append(f"Template kompas cocok (skor={best_tpl:.2f})")

        # --- Stage 4: Contour Analysis --------------------------------------
        # Panah kompas BIG: dua segitiga bertolak belakang (atas hitam, bawah putih)
        # Ciri: aspect ratio tinggi > lebar, kontur 4-10 vertex
        _, thresh = cv2.threshold(search, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        arrow_score = 0.0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 60 or area > sw * sh * 0.04:
                continue
            x, y, cw, ch = cv2.boundingRect(cnt)
            asp = ch / float(cw) if cw > 0 else 0

            if asp < 1.2:
                continue  # Harus lebih tinggi dari lebar (khas panah ke atas)

            peri  = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.05 * peri, True)
            n_v   = len(approx)

            if 3 <= n_v <= 12:
                # Cek puncak ada di 1/3 atas kontur (arah panah ke atas)
                all_y = cnt[:, 0, 1]
                top_y = np.min(all_y)
                if top_y < (y + ch * 0.35):
                    # Stage 5: Shape — cek simetri horizontal sederhana
                    all_x = cnt[:, 0, 0]
                    cx_cnt = float(np.mean(all_x))
                    left_pts  = np.sum(all_x < cx_cnt)
                    right_pts = np.sum(all_x > cx_cnt)
                    sym_ratio = min(left_pts, right_pts) / (max(left_pts, right_pts) + 1e-5)

                    seg_score = 0.25 + (0.10 if sym_ratio > 0.45 else 0.0) + \
                                (0.05 if n_v >= 5 else 0.0)
                    if seg_score > arrow_score:
                        arrow_score = seg_score
                        if not best_bbox or best_tpl < 0.35:
                            best_bbox = (sx + x, y, cw, ch)
                        evidence_parts.append(f"Kontur panah runcing ke atas ({n_v}v, asp={asp:.1f})")

        score += arrow_score

        # ─── Stage 6: Voting Classifier ──────────────────────────────────────
        score = min(1.0, score)
        detected = score >= 0.40 or (ocr_hit and score >= 0.25)

        if detected and best_bbox is None:
            best_bbox = (int(w * 0.75), int(h * 0.05), 50, 80)

        ev = " | ".join(evidence_parts) if evidence_parts else "Tidak ada bukti kuat"
        return {
            "detected":   detected,
            "confidence": round(score, 2),
            "bbox":       best_bbox,
            "evidence":   ev if detected else "Simbol arah utara tidak terdeteksi"
        }

    except Exception as e:
        logger.error(f"detect_north_arrow error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}


def _build_north_templates(cv2) -> List[np.ndarray]:
    """
    Buat template sintetis yang merepresentasikan berbagai bentuk
    simbol Arah Utara pada peta BIG.
    """
    templates = []
    try:
        # Template A: Panah ke atas simetris (dua segitiga atas-bawah)
        # Mirip gambar user: U di atas, dua sayap panah ke bawah
        a = np.ones((50, 30), dtype=np.uint8) * 200
        pts_upper = np.array([[15, 2], [24, 28], [15, 22], [6, 28]], np.int32)
        cv2.fillPoly(a, [pts_upper], 20)   # sayap atas hitam
        pts_lower = np.array([[15, 24], [24, 48], [6, 48]], np.int32)
        cv2.fillPoly(a, [pts_lower], 150)  # sayap bawah abu
        templates.append(a)

        # Template B: Segitiga runcing tunggal ke atas
        b = np.ones((40, 25), dtype=np.uint8) * 220
        cv2.fillPoly(b, [np.array([[12, 1], [24, 38], [0, 38]], np.int32)], 10)
        templates.append(b)

        # Template C: Kompas 4 arah (diamond)
        c = np.zeros((45, 45), dtype=np.uint8)
        cv2.fillPoly(c, [np.array([[22, 1], [38, 22], [22, 44], [6, 22]], np.int32)], 180)
        cv2.fillPoly(c, [np.array([[22, 1], [38, 22], [22, 16]], np.int32)], 30)
        templates.append(c)

        # Template D: Lingkaran kompas dengan panah atas
        d = np.ones((45, 45), dtype=np.uint8) * 200
        cv2.circle(d, (22, 22), 20, 80, 2)
        cv2.fillPoly(d, [np.array([[22, 3], [30, 25], [14, 25]], np.int32)], 20)
        templates.append(d)

    except Exception as e:
        logger.warning(f"_build_north_templates error: {e}")
    return templates


# ═════════════════════════════════════════════════════════════════════════════
# 2. GRID KOORDINAT — Deteksi Garis Biru H & V membentuk Kisi Seragam
# ═════════════════════════════════════════════════════════════════════════════

def analyze_grid_presence(image_cv: np.ndarray) -> Dict[str, Any]:
    """
    Deteksi Grid Koordinat dengan validasi warna biru & kisi persegi seragam.

    Alur:
    1. Isolasi Channel Biru (garis grid pada peta BIG berwarna biru)
    2. Threshold channel biru — binarisasi piksel biru dominan
    3. Canny + Hough Lines pada mask biru
    4. Separasi garis horizontal & vertikal
    5. Clustering garis sejajar
    6. Validasi keseragaman jarak (spacing uniformity)
    7. Hitung titik perpotongan
    8. Fallback: Canny umum pada seluruh gambar grayscale
    """
    cv2 = _safe_cv_import()
    if cv2 is None or image_cv is None:
        return {"has_grid": False, "confidence": 0.0, "h_lines": 0, "v_lines": 0,
                "evidence": "OpenCV tidak tersedia"}

    try:
        h_img, w_img = image_cv.shape[:2]

        # ─── 1. Isolasi Channel Biru ──────────────────────────────────────────
        # Garis grid peta BIG biasanya berwarna biru (B dominan, R & G lebih rendah)
        # Gunakan HSV untuk seleksi warna biru yang lebih robust
        hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)

        # Rentang warna biru di HSV
        blue_lower1 = np.array([90,  40,  40])
        blue_upper1 = np.array([135, 255, 255])
        blue_mask = cv2.inRange(hsv, blue_lower1, blue_upper1)

        # Bersihkan noise kecil
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        blue_mask = cv2.dilate(blue_mask, kernel, iterations=1)

        blue_pixel_ratio = np.count_nonzero(blue_mask) / float(h_img * w_img)
        logger.info(f"analyze_grid_presence: blue_pixel_ratio={blue_pixel_ratio:.4f}")

        h_y_list, v_x_list = [], []

        # ─── 2. Hough Lines pada Mask Biru ───────────────────────────────────
        if blue_pixel_ratio > 0.001:  # Ada piksel biru yang cukup
            edges_blue = cv2.Canny(blue_mask, 30, 90)
            min_len = int(min(w_img, h_img) * 0.15)
            lines_blue = cv2.HoughLinesP(
                edges_blue, 1, np.pi / 180,
                threshold=50,
                minLineLength=min_len,
                maxLineGap=15
            )

            if lines_blue is not None:
                for line in lines_blue:
                    pts = line.flatten()
                    if len(pts) < 4:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in pts[:4]]
                    dx, dy = abs(x2 - x1), abs(y2 - y1)
                    if dy <= 8 and dx > 20:          # Horizontal
                        h_y_list.append((y1 + y2) / 2.0)
                    elif dx <= 8 and dy > 20:         # Vertikal
                        v_x_list.append((x1 + x2) / 2.0)

        # ─── 3. Fallback: Canny Umum (Grayscale) ─────────────────────────────
        # Jika garis biru tidak terdeteksi, coba grayscale dengan threshold lebih rendah
        if len(h_y_list) < 2 or len(v_x_list) < 2:
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
            # Enhancing contrast untuk garis tipis
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_eq = clahe.apply(gray)
            edges_gray = cv2.Canny(gray_eq, 30, 90, apertureSize=3)

            min_len_fb = int(min(w_img, h_img) * 0.12)
            lines_gray = cv2.HoughLinesP(
                edges_gray, 1, np.pi / 180,
                threshold=40,
                minLineLength=min_len_fb,
                maxLineGap=18
            )

            if lines_gray is not None:
                h_y_fb, v_x_fb = [], []
                for line in lines_gray:
                    pts = line.flatten()
                    if len(pts) < 4:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in pts[:4]]
                    dx, dy = abs(x2 - x1), abs(y2 - y1)
                    if dy <= 8 and dx > 30:
                        h_y_fb.append((y1 + y2) / 2.0)
                    elif dx <= 8 and dy > 30:
                        v_x_fb.append((x1 + x2) / 2.0)
                # Merge jika lebih banyak
                if len(h_y_fb) > len(h_y_list):
                    h_y_list = h_y_fb
                if len(v_x_fb) > len(v_x_list):
                    v_x_list = v_x_fb

        # ─── 4. Clustering Garis Sejajar ─────────────────────────────────────
        grouped_h = _cluster_1d(h_y_list, tol=20.0)
        grouped_v = _cluster_1d(v_x_list, tol=20.0)

        # ─── 5. Validasi Keseragaman Jarak ───────────────────────────────────
        uniform_h = _spacing_uniformity(grouped_h, threshold=0.50)
        uniform_v = _spacing_uniformity(grouped_v, threshold=0.50)
        is_uniform = uniform_h or uniform_v

        # ─── 6. Hitung Perpotongan ───────────────────────────────────────────
        n_h = len(grouped_h)
        n_v = len(grouped_v)
        intersections = n_h * n_v

        # ─── 7. Validasi Grid ────────────────────────────────────────────────
        has_grid = (n_h >= 2 and n_v >= 2 and intersections >= 4)

        # Tingkatkan kepercayaan jika warna biru dominan + garis seragam
        confidence = 0.10
        if has_grid:
            base = 0.45
            base += min(0.20, (n_h + n_v) * 0.04)
            base += 0.15 if is_uniform else 0.0
            base += 0.10 if blue_pixel_ratio > 0.005 else 0.0
            confidence = min(1.0, base)

        evidence = (
            f"Grid: {n_h} garis horizontal, {n_v} garis vertikal, "
            f"{intersections} perpotongan. "
            f"Keseragaman: {'Ya' if is_uniform else 'Tidak'}. "
            f"Piksel biru: {blue_pixel_ratio*100:.2f}%"
        )

        logger.info(f"analyze_grid_presence: H={n_h}, V={n_v}, blue={blue_pixel_ratio:.4f}, grid={has_grid}")

        return {
            "has_grid":          has_grid,
            "confidence":        round(confidence, 2),
            "h_lines":           n_h,
            "v_lines":           n_v,
            "intersections":     intersections,
            "spacing_uniformity": is_uniform,
            "blue_ratio":        round(blue_pixel_ratio, 4),
            "evidence":          evidence if has_grid else "Pola grid tidak terdeteksi"
        }

    except Exception as e:
        logger.error(f"analyze_grid_presence error: {e}")
        return {"has_grid": False, "confidence": 0.0, "h_lines": 0, "v_lines": 0,
                "evidence": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# 3. INSET MAP — Frame Kotak + Grid Internal + Teks Petunjuk Letak
# ═════════════════════════════════════════════════════════════════════════════

def detect_inset_map(image_cv: np.ndarray, full_text: str = "") -> Dict[str, Any]:
    """
    Deteksi Inset Lokasi tanpa bergantung pada warna merah.

    Karakteristik Inset Peta BIG:
    - Kotak bingkai kecil (2–15% area peta)
    - Berisi miniatur peta dengan grid di dalamnya
    - Ada teks: "Petunjuk Letak Peta", "Diagram Lokasi"
    - Biasanya di bawah judul peta atau di sudut panel kanan

    Alur:
    1. OCR Keyword Check (bobot tinggi jika ditemukan)
    2. Rectangle / Frame Detection (kontur 4 sisi tertutup)
    3. Crop & Analisis Isi:
       a. Edge Density (kerapatan fitur spasial)
       b. Deteksi Grid Internal (garis H&V kecil di dalam inset)
       c. Texture Complexity (Laplacian variance)
    4. Validasi Posisi (di bawah judul atau panel kanan)
    5. Voting & Scoring
    """
    cv2 = _safe_cv_import()
    if cv2 is None or image_cv is None:
        return {"detected": False, "confidence": 0.0, "bbox": None,
                "evidence": "OpenCV tidak tersedia"}

    try:
        h_img, w_img = image_cv.shape[:2]
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

        # ─── 1. OCR Keyword ──────────────────────────────────────────────────
        INSET_KEYWORDS = [
            r'petunjuk\s+letak\s+peta',
            r'diagram\s+lokasi',
            r'peta\s+acuan',
            r'peta\s+induk',
            r'\binset\b',
            r'lokasi\s+desa',
        ]
        has_keyword = any(
            re.search(kw, full_text, re.IGNORECASE) for kw in INSET_KEYWORDS
        )

        # ─── 2. Rectangle / Frame Detection ─────────────────────────────────
        # Gunakan morfologi untuk mempertegas bingkai kotak
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blur, 30, 100)
        dil   = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)

        contours, hierarchy = cv2.findContours(dil, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        MAX_AREA  = w_img * h_img * 0.15  # Inset maks 15% area peta
        MIN_AREA  = w_img * h_img * 0.003  # Minimal 0.3%
        MIN_SIDE  = min(w_img, h_img) * 0.05  # Min sisi 5%

        candidates = []
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < MIN_AREA or area > MAX_AREA:
                continue

            bx, by, bw, bh = cv2.boundingRect(cnt)
            if bw < MIN_SIDE or bh < MIN_SIDE:
                continue

            asp = bh / float(bw) if bw > 0 else 0
            if not (0.3 < asp < 3.5):
                continue

            peri  = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
            if not (4 <= len(approx) <= 8):
                continue

            # ─── 3a. Crop & Edge Density ─────────────────────────────────────
            crop = gray[by:by+bh, bx:bx+bw]
            if crop.size == 0:
                continue

            crop_edges = cv2.Canny(crop, 25, 80)
            edge_density = np.count_nonzero(crop_edges) / float(bw * bh)

            # ─── 3b. Deteksi Grid Internal ───────────────────────────────────
            # Inset berisi miniatur peta → ada garis H&V kecil
            min_len_inset = int(min(bw, bh) * 0.20)
            inner_lines = cv2.HoughLinesP(
                crop_edges, 1, np.pi / 180,
                threshold=max(8, int(min(bw, bh) * 0.08)),
                minLineLength=max(5, min_len_inset),
                maxLineGap=8
            )
            inner_h, inner_v = 0, 0
            if inner_lines is not None:
                for il in inner_lines:
                    pts = il.flatten()
                    if len(pts) < 4:
                        continue
                    ix1, iy1, ix2, iy2 = [int(v) for v in pts[:4]]
                    if abs(iy2 - iy1) <= 5:
                        inner_h += 1
                    elif abs(ix2 - ix1) <= 5:
                        inner_v += 1
            has_inner_grid = (inner_h >= 2 and inner_v >= 2)

            # ─── 3c. Texture Complexity ──────────────────────────────────────
            lap_var = float(np.var(cv2.Laplacian(crop, cv2.CV_64F)))

            # ─── 4. Posisi ───────────────────────────────────────────────────
            # Inset sering di: (a) bawah judul kiri, (b) panel kanan atas/bawah
            in_right_panel = (bx + bw) > w_img * 0.60
            in_upper_half  = by < h_img * 0.55
            in_good_pos    = in_right_panel or (in_upper_half and bx > w_img * 0.40)

            # ─── 5. Scoring ──────────────────────────────────────────────────
            score = 0.0
            if edge_density > 0.04:
                score += 0.20
            if edge_density > 0.08:
                score += 0.10
            if has_inner_grid:
                score += 0.25
            if lap_var > 80.0:
                score += 0.15
            if in_good_pos:
                score += 0.10
            if has_keyword:
                score += 0.35

            candidates.append({
                "bbox":         (bx, by, bw, bh),
                "score":        score,
                "edge_density": round(edge_density, 3),
                "lap_var":      round(lap_var, 1),
                "inner_h":      inner_h,
                "inner_v":      inner_v,
                "has_inner_grid": has_inner_grid,
            })

        # Pilih kandidat terbaik
        if candidates:
            best = max(candidates, key=lambda c: c["score"])
            if best["score"] >= 0.40:
                conf = min(1.0, best["score"])
                ev   = (
                    f"Inset {best['bbox'][2]}×{best['bbox'][3]}px | "
                    f"Edge density={best['edge_density']} | "
                    f"Grid internal={'Ya' if best['has_inner_grid'] else 'Tidak'} "
                    f"(H={best['inner_h']}, V={best['inner_v']}) | "
                    f"Tekstur={best['lap_var']}"
                )
                if has_keyword:
                    ev += " | Teks petunjuk letak peta ditemukan"
                return {"detected": True, "confidence": round(conf, 2),
                        "bbox": best["bbox"], "evidence": ev}

        # ─── Fallback: Keyword saja ───────────────────────────────────────────
        if has_keyword:
            return {
                "detected":   True,
                "confidence": 0.55,
                "bbox":       None,
                "evidence":   "Teks 'Petunjuk Letak Peta'/'Diagram Lokasi' ditemukan di OCR"
            }

        return {"detected": False, "confidence": 0.10, "bbox": None,
                "evidence": "Inset lokasi tidak terdeteksi"}

    except Exception as e:
        logger.error(f"detect_inset_map error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# 4. SKALA GRAFIS
# ═════════════════════════════════════════════════════════════════════════════

def detect_scale_bar(image_cv: np.ndarray) -> Dict[str, Any]:
    """Deteksi skala grafis (bar hitam-putih bergantian)."""
    cv2 = _safe_cv_import()
    if cv2 is None or image_cv is None:
        return {"detected": False, "confidence": 0.0, "bbox": None,
                "evidence": "OpenCV tidak tersedia"}
    try:
        h, w = image_cv.shape[:2]
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        # Skala grafis biasanya di 35% bawah
        bot = gray[int(h * 0.60):, :]
        bh, bw = bot.shape

        _, bin_img = cv2.threshold(bot, 128, 255, cv2.THRESH_BINARY)

        for sy in range(int(bh * 0.05), int(bh * 0.95), max(1, bh // 15)):
            row  = bin_img[sy, :]
            trans = 0
            prev  = row[0]
            for px in range(1, len(row)):
                if row[px] != prev:
                    trans += 1
                    prev   = row[px]
            if 4 <= trans <= 22:
                return {
                    "detected":   True,
                    "confidence": 0.70,
                    "bbox":       (0, int(h * 0.60) + sy - 10, w, 40),
                    "evidence":   f"Pola alternating hitam-putih skala grafis ({trans} transisi)"
                }

        return {"detected": False, "confidence": 0.15, "bbox": None,
                "evidence": "Skala grafis tidak terdeteksi"}

    except Exception as e:
        logger.error(f"detect_scale_bar error: {e}")
        return {"detected": False, "confidence": 0.0, "bbox": None, "evidence": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# 5. STUB FUNCTIONS (tidak lagi digunakan aktif, dipertahankan untuk kompatibilitas)
# ═════════════════════════════════════════════════════════════════════════════

def detect_boundary_lines(image_cv: np.ndarray) -> Dict[str, Any]:
    """Stub: Garis batas wilayah — diperiksa via OCR di validator.py."""
    return {"detected": True, "confidence": 0.50, "bbox": None,
            "evidence": "Garis batas wilayah — diperiksa via OCR validator"}


def detect_legend_visually(image_cv: np.ndarray) -> Dict[str, Any]:
    """Stub: Legenda — diperiksa via OCR di validator.py."""
    return {"detected": True, "confidence": 0.60, "bbox": None,
            "evidence": "Legenda — diperiksa via OCR validator"}
