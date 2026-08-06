"""
table_reader.py — Modul Ekstraksi & Parsing Tabel Titik Kartometrik
===================================================================
Alur Ekstraksi & Parsing Bertahap (Tahap 3 - Tahap 8):

Tahap 3: Deteksi Area Tabel (OCR + Rule Based)
  - Keyword: "DAFTAR TITIK KARTOMETRIK", "TITIK KARTOMETRIK", "DAFTAR KOORDINAT", "KOORDINAT TITIK"
  - Output: Bounding Box (x, y, w, h)

Tahap 4: Crop Area Tabel (Computer Vision + OCR)
  - Crop hanya area tabel & jalankan OCR ulang hanya pada area crop tersebut.

Tahap 5: Deteksi Struktur Tabel (Computer Vision)
  - Morphological kernel & contour line detection -> "lined" vs "unlined".

Tahap 6A: Ekstraksi Sel (OpenCV + OCR pada setiap sel individual untuk tabel bergaris)
Tahap 6B: Parsing Baris (OCR + Rule Based untuk tabel tidak bergaris)

Tahap 7: Identifikasi Jenis Data (Regex + Rule Based Classifier)
  - TYPE_KODE (TK.xxx, TK-xxx, TKxxx)
  - TYPE_LINTANG (6°xx'xx" LS / LU)
  - TYPE_BUJUR (113°xx'xx" BT / BB)
  - TYPE_X (UTM Easting desimal, misal 827536.15)
  - TYPE_Y (UTM Northing desimal, misal 9228990.16)

Tahap 8: State Machine Parser
  - State machine diawali oleh TYPE_KODE. Tidak bergantung pada kolom NO!
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("peta_audit.table_reader")


# ═════════════════════════════════════════════════════════════════════════════
# TAHAP 7: IDENTIFIKASI JENIS DATA (TOKEN DATA CLASSIFIER)
# ═════════════════════════════════════════════════════════════════════════════

# Regex khusus untuk Kode Titik Kartometrik: TK.35.29.16.2002-19.2009-000, TK-001, TK001, TK.001, TK 35.29...
RE_KODE_TK = re.compile(r'\b(TK[\.\ \-_]?[A-Za-z0-9\.\-_ ]{1,70})\b', re.IGNORECASE)
# RE_KODE_ALT: hanya cocok jika ada separator (titik/strip) dan minimal 3 karakter setelahnya
# Ini mencegah false positive seperti "Jl", "Ds", dll.
RE_KODE_ALT = re.compile(r'\b([A-Za-z]{1,4}[\.\-_][A-Za-z0-9\.\-_]{3,30})\b')

RE_EXCLUDE_WORDS = re.compile(
    r'^(PETA|BATAS|DESA|KELURAHAN|KECAMATAN|KABUPATEN|PROVINSI|DAFTAR|TITIK|KARTOMETRIK|KOORDINAT|LEGENDA|LAMPIRAN|SKALA|DATUM|PROYEKSI|SISTEM|GRID|UTM|NO|X|Y|LS|LU|BT|BB|DIBUAT|DITANDATANGANI|JL|JALAN|DSN|DUSUN|RT|RW|RK|GANG|GG|BLOK|BLK|NAMA|WILAYAH|BARAT|TIMUR|SELATAN|UTARA|TENGAH|DMS|DM|DD|DS|KP|KEC|KAB|PROV|KOTA)$',
    re.IGNORECASE
)

# Regex Lintang (Wajib ada LS atau LU atau S/N suffix) - mendukung berbagai format DMS
RE_LINTANG = re.compile(
    r'(\d{1,2}\s*[\u00b0°0oO\*\s]\s*\d{1,2}\s*[\'\u2032`\s]\s*\d{1,2}(?:[\.,]\d+)?\s*[\"\u2033\'`\s]{0,2}\s*(?:LS|LU|S|N))\b',
    re.IGNORECASE
)
RE_LINTANG_SIMPLE = re.compile(r'(\d{1,2}(?:[\.,]\d+)?\s*[\u00b0°]?\s*(?:LS|LU))\b', re.IGNORECASE)

# Regex Bujur (Wajib ada BT atau BB atau E/W suffix)
RE_BUJUR = re.compile(
    r'(\d{1,3}\s*[\u00b0°0oO\*\s]\s*\d{1,2}\s*[\'\u2032`\s]\s*\d{1,2}(?:[\.,]\d+)?\s*[\"\u2033\'`\s]{0,2}\s*(?:BT|BB|E|W))\b',
    re.IGNORECASE
)
RE_BUJUR_SIMPLE = re.compile(r'(\d{1,3}(?:[\.,]\d+)?\s*[\u00b0°]?\s*(?:BT|BB))\b', re.IGNORECASE)

# Regex UTM Desimal (X dan Y) - 5-7 digit dengan opsional desimal (mendukung koma sebagai pemisah desimal)
RE_UTM_NUM = re.compile(r'\b(\d{5,7}(?:[\.,]\d{1,4})?)\b')

# Regex untuk mendeteksi apakah sel mengandung nilai kode TK yang valid
# Mendukung format: TK.xxx, TK-xxx, TK xxx (dengan spasi)
RE_VALID_TK_KODE = re.compile(r'\bTK[\.\ \-_]', re.IGNORECASE)


def classify_data_tokens_in_text(text: str) -> List[Tuple[str, str]]:
    """
    Tahap 7: Identifikasi Jenis Data
    Menganalisis pola teks dan mengklasifikasikannya ke dalam tipe token:
    - TYPE_KODE
    - TYPE_LINTANG
    - TYPE_BUJUR
    - TYPE_X
    - TYPE_Y
    """
    tokens: List[Tuple[str, str]] = []
    lines = text.split('\n')

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        # Skip header baris judul (hanya jika baris tersebut adalah murni baris header, bukan baris data dengan NO)
        if re.search(r'^\s*(DAFTAR|NO|NO\.|NOMOR|TITIK KARTOMETRIK|LINTANG|BUJUR|X\(M\)|Y\(M\)|KODE TITIK|NOMOR TITIK)\s*$', line_str, re.IGNORECASE) or \
           (re.search(r'\b(LINTANG|BUJUR|KODE TITIK|TITIK BATAS|NOMOR TITIK)\b', line_str, re.IGNORECASE) and not RE_UTM_NUM.search(line_str) and not RE_LINTANG.search(line_str)):
            continue

        # 1. Cari Lintang (LS/LU)
        lintang_found = ""
        m_lat = RE_LINTANG.search(line_str)
        if m_lat:
            lintang_found = m_lat.group(1).strip()
        else:
            m_lat_s = RE_LINTANG_SIMPLE.search(line_str)
            if m_lat_s:
                lintang_found = m_lat_s.group(1).strip()

        # 2. Cari Bujur (BT/BB)
        bujur_found = ""
        m_lon = RE_BUJUR.search(line_str)
        if m_lon:
            bujur_found = m_lon.group(1).strip()
        else:
            m_lon_s = RE_BUJUR_SIMPLE.search(line_str)
            if m_lon_s:
                bujur_found = m_lon_s.group(1).strip()

        # 3. Cari Kode Titik Kartometrik
        kode_found = ""
        m_tk = RE_KODE_TK.search(line_str)
        if m_tk:
            kode_found = m_tk.group(1).strip()
        else:
            m_alt = RE_KODE_ALT.search(line_str)
            if m_alt and not RE_EXCLUDE_WORDS.match(m_alt.group(1)):
                kode_found = m_alt.group(1).strip()

        # 4. Cari Koordinat UTM (X dan Y)
        line_clean = line_str
        if lintang_found:
            line_clean = line_clean.replace(lintang_found, ' ')
        if bujur_found:
            line_clean = line_clean.replace(bujur_found, ' ')
        if kode_found:
            line_clean = line_clean.replace(kode_found, ' ')

        utm_matches = RE_UTM_NUM.findall(line_clean)
        x_found = ""
        y_found = ""

        if len(utm_matches) >= 2:
            x_found = utm_matches[0].strip()
            y_found = utm_matches[1].strip()
        elif len(utm_matches) == 1:
            try:
                num = float(utm_matches[0].replace(',', '.'))
                if num > 2000000:
                    y_found = utm_matches[0].strip()
                else:
                    x_found = utm_matches[0].strip()
            except ValueError:
                pass

        # Tambahkan token terklasifikasi ke list
        if kode_found:
            tokens.append(("TYPE_KODE", kode_found))
        if lintang_found:
            tokens.append(("TYPE_LINTANG", lintang_found))
        if bujur_found:
            tokens.append(("TYPE_BUJUR", bujur_found))
        if x_found:
            tokens.append(("TYPE_X", x_found))
        if y_found:
            tokens.append(("TYPE_Y", y_found))

    return tokens


# ═════════════════════════════════════════════════════════════════════════════
# TAHAP 8: STATE MACHINE PARSER
# ═════════════════════════════════════════════════════════════════════════════

def parse_with_state_machine(tokens: List[Tuple[str, str]]) -> List[Dict[str, str]]:
    """
    Tahap 8: State Machine Parser
    Sistem tidak bergantung pada kolom NO.
    Gunakan TYPE_KODE sebagai penanda awal record.

    Flow State Machine:
    START / WAIT_KODE
      ↓ (Terima TYPE_KODE)
    RECORD_ACTIVE -> Mulai Record
      ↓ (Isi TYPE_LINTANG, TYPE_BUJUR, TYPE_X, TYPE_Y)
    Terima TYPE_KODE berikutnya -> Simpan record sebelumnya & Mulai Record Baru
    """
    rows: List[Dict[str, str]] = []
    current_record: Optional[Dict[str, str]] = None
    record_idx = 1

    def _commit_record(rec: Dict[str, str]):
        nonlocal record_idx
        if rec and rec.get("kode"):
            # Record valid jika memiliki kode DAN minimal salah satu koordinat
            has_coords = bool(rec.get("lintang") or rec.get("x") or rec.get("bujur") or rec.get("y"))
            if has_coords:
                no_str = str(record_idx)
                final_rec = {
                    "no": no_str,
                    "kode": rec.get("kode", ""),
                    "lintang": rec.get("lintang", ""),
                    "bujur": rec.get("bujur", ""),
                    "x": rec.get("x", ""),
                    "y": rec.get("y", ""),

                    # Standardized capital keys
                    "NO": no_str,
                    "TITIK KARTOMETRIK": rec.get("kode", ""),
                    "LINTANG": rec.get("lintang", ""),
                    "BUJUR": rec.get("bujur", ""),
                    "X(M)": rec.get("x", ""),
                    "Y(M)": rec.get("y", "")
                }
                rows.append(final_rec)
                record_idx += 1

    for token_type, token_val in tokens:
        if token_type == "TYPE_KODE":
            # Jika ada record aktif sebelumnya, commit record tersebut
            if current_record is not None:
                _commit_record(current_record)

            # Mulai record baru (START)
            current_record = {
                "kode": token_val,
                "lintang": "",
                "bujur": "",
                "x": "",
                "y": ""
            }

        elif current_record is not None:
            if token_type == "TYPE_LINTANG" and not current_record["lintang"]:
                current_record["lintang"] = token_val
            elif token_type == "TYPE_BUJUR" and not current_record["bujur"]:
                current_record["bujur"] = token_val
            elif token_type == "TYPE_X" and not current_record["x"]:
                current_record["x"] = token_val
            elif token_type == "TYPE_Y" and not current_record["y"]:
                current_record["y"] = token_val

    # Commit record terakhir jika ada
    if current_record is not None:
        _commit_record(current_record)

    return rows


# ═════════════════════════════════════════════════════════════════════════════
# TAHAP 3 & 4: DETEKSI AREA TABEL & CROP (OCR + COMPUTER VISION)
# ═════════════════════════════════════════════════════════════════════════════

def detect_and_crop_table_area(
    image_cv: np.ndarray,
    full_text: str = ""
) -> Tuple[Optional[np.ndarray], Tuple[int, int, int, int], str]:
    """
    Tahap 3 & 4: Deteksi & Crop Area Tabel
    - Cari keyword utama "DAFTAR TITIK KARTOMETRIK"
      Alternatif: "TITIK KARTOMETRIK", "DAFTAR KOORDINAT", "KOORDINAT TITIK"
    - Tentukan Bounding Box area tabel (x, y, w, h)
    - Crop hanya area tabel & jalankan OCR ulang hanya pada area crop tersebut.
    """
    if image_cv is None:
        return None, (0, 0, 0, 0), ""

    h, w = image_cv.shape[:2]

    # Keyword pencarian area tabel (berdasarkan prioritas)
    keywords = [
        "DAFTAR TITIK KARTOMETRIK",
        "TITIK KARTOMETRIK",
        "DAFTAR KOORDINAT",
        "KOORDINAT TITIK"
    ]

    table_top = int(h * 0.35)  # Default jika tidak terdeteksi
    found_keyword = None

    # Coba cari keyword dalam teks penuh
    for kw in keywords:
        if re.search(re.escape(kw), full_text, re.IGNORECASE):
            found_keyword = kw
            logger.info(f"Tahap 3: Keyword tabel '{kw}' terdeteksi dalam teks.")
            break

    # Cek lokasi visual keyword dengan pytesseract image_to_data jika Tesseract tersedia
    bbox_table = (0, table_top, w, h - table_top)
    try:
        import pytesseract
        from PIL import Image

        pil_img = Image.fromarray(image_cv[:, :, ::-1])
        ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)

        n_boxes = len(ocr_data.get("text", []))
        for i in range(n_boxes):
            word = ocr_data["text"][i].strip().upper()
            if word in ("DAFTAR", "TITIK", "KARTOMETRIK", "KOORDINAT"):
                top_y = ocr_data["top"][i]
                if top_y > 50:  # Abaikan header paling atas jika terlalu kecil
                    table_top = max(0, top_y - 15)
                    bbox_table = (0, table_top, w, h - table_top)
                    logger.info(f"Tahap 3: Posisi visual tabel terdeteksi di y={table_top}")
                    break
    except Exception as e:
        logger.warning(f"Deteksi visual OCR data gagal: {e}")

    # Tahap 4: Crop area tabel
    crop_x, crop_y, crop_w, crop_h = bbox_table
    crop_img = image_cv[crop_y:crop_y+crop_h, crop_x:crop_x+crop_w]

    # OCR ulang HANYA pada area crop tabel
    crop_ocr_text = ""
    try:
        import pytesseract
        from PIL import Image
        pil_crop = Image.fromarray(crop_img[:, :, ::-1])
        crop_ocr_text = pytesseract.image_to_string(pil_crop, config="--oem 3 --psm 6")
        logger.info(f"Tahap 4: OCR ulang area crop tabel ({crop_w}x{crop_h} px) menghasilkan {len(crop_ocr_text)} karakter.")
    except Exception as e:
        logger.warning(f"Tahap 4: OCR crop area tabel gagal: {e}")

    return crop_img, bbox_table, crop_ocr_text


# ═════════════════════════════════════════════════════════════════════════════
# TAHAP 5 & 6: DETEKSI STRUKTUR TABEL & EKSTRAKSI (SEL VS BARIS)
# ═════════════════════════════════════════════════════════════════════════════

def detect_table_structure(crop_img: np.ndarray) -> str:
    """
    Tahap 5: Deteksi Struktur Tabel (Bergaris / Lined vs Tidak Bergaris / Unlined)
    Menggunakan Morphology, Contour Detection, dan Hough Line.
    """
    if crop_img is None or crop_img.size == 0:
        return "unlined"

    try:
        import cv2
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        h, w = crop_img.shape[:2]

        # Morphology kernel horizontal & vertikal
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 20), 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, h // 20)))

        img_h = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h)
        img_v = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_v)

        cnts_h, _ = cv2.findContours(img_h, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts_v, _ = cv2.findContours(img_v, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h_lines = len(cnts_h)
        v_lines = len(cnts_v)

        logger.info(f"Tahap 5: Deteksi garis tabel (H-lines={h_lines}, V-lines={v_lines})")

        if h_lines >= 3 and v_lines >= 2:
            return "lined"  # Tabel bergaris
        return "unlined"     # Tabel tidak bergaris

    except Exception as e:
        logger.warning(f"Tahap 5 error: {e}")
        return "unlined"


def extract_table_cells_6a(crop_img: np.ndarray) -> str:
    """
    Tahap 6A: Ekstraksi Sel (Tabel Bergaris)
    Deteksi seluruh sel dan lakukan OCR pada setiap sel individual.
    """
    if crop_img is None or crop_img.size == 0:
        return ""

    try:
        import cv2
        import pytesseract
        from PIL import Image

        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        h, w = crop_img.shape[:2]
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 25), 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, h // 25)))

        img_h = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h)
        img_v = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_v)

        table_mask = cv2.add(img_h, img_v)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        cell_boxes = []
        for cnt in contours:
            cx, cy, cw, ch = cv2.boundingRect(cnt)
            if 20 < cw < w * 0.8 and 12 < ch < h * 0.4:
                cell_boxes.append((cy, cx, cw, ch))

        # Urutkan sel dari atas ke bawah, kiri ke kanan
        cell_boxes.sort(key=lambda b: (b[0] // 20, b[1]))

        cell_texts = []
        last_y_group = -1
        current_row_texts = []

        for cy, cx, cw, ch in cell_boxes:
            cell_crop = crop_img[cy:cy+ch, cx:cx+cw]
            if cell_crop.size == 0:
                continue

            pil_cell = Image.fromarray(cell_crop[:, :, ::-1])
            cell_txt = pytesseract.image_to_string(pil_cell, config="--oem 3 --psm 6").strip()

            y_group = cy // 20
            if last_y_group != -1 and y_group != last_y_group:
                cell_texts.append("  ".join(current_row_texts))
                current_row_texts = []

            last_y_group = y_group
            if cell_txt:
                current_row_texts.append(cell_txt)

        if current_row_texts:
            cell_texts.append("  ".join(current_row_texts))

        return "\n".join(cell_texts)

    except Exception as e:
        logger.warning(f"Tahap 6A cell extraction error: {e}")
        return ""


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT UTAMA EKSTRAKSI TABEL TITIK KARTOMETRIK
# ═════════════════════════════════════════════════════════════════════════════

def _extract_structured_table_from_page(page) -> List[Dict]:
    """
    Ekstraksi terstruktur dari satu halaman pdfplumber menggunakan deteksi header kolom.
    Mendukung tabel DENGAN maupun TANPA kolom NO / No. / Nomor.
    Mencari kolom: NO, KODE TITIK, LINTANG, BUJUR, X, Y secara otomatis dari baris header.
    """
    rows_out: List[Dict] = []

    try:
        tables = page.extract_tables()
    except Exception as e:
        logger.warning(f"extract_tables gagal: {e}")
        return rows_out

    for tbl in tables:
        if not tbl or len(tbl) < 2:
            continue

        # ── Deteksi baris header kolom (cari di 8 baris pertama) ──
        col_no = col_kode = col_lintang = col_bujur = col_x = col_y = -1
        header_row_idx = -1

        for ri, row in enumerate(tbl[:8]):
            if not row:
                continue

            tmp_no = tmp_kode = tmp_lat = tmp_lon = tmp_x = tmp_y = -1

            for ci, cell in enumerate(row):
                cell_u = str(cell or "").upper().strip().replace("\n", " ")
                if not cell_u:
                    continue

                # 1. Kolom Nomor Urut (NO / NO. / NOMOR / NUM / NO URUT)
                if re.search(r'^\s*(NO|NO\.|NOMOR|NUM|NUMBER|NO\s*URUT|NO\.URUT)\s*$', cell_u):
                    if tmp_no == -1:
                        tmp_no = ci
                    continue

                # 2. Kolom Lintang (LINTANG / LATITUDE / LAT)
                if re.search(r'\b(LINTANG|LATITUDE|LAT)\b', cell_u):
                    if tmp_lat == -1:
                        tmp_lat = ci
                    continue

                # 3. Kolom Bujur (BUJUR / LONGITUDE / LON)
                if re.search(r'\b(BUJUR|LONGITUDE|LON)\b', cell_u):
                    if tmp_lon == -1:
                        tmp_lon = ci
                    continue

                # 4. Kolom X (UTM X / X UTM / X (UTM) / X (M) / EASTING / X)
                if re.search(r'\b(UTM\s*X|X\s*UTM|EASTING)\b|\bX\b', cell_u):
                    if tmp_x == -1:
                        tmp_x = ci
                    continue

                # 5. Kolom Y (UTM Y / Y UTM / Y (UTM) / Y (M) / NORTHING / Y)
                if re.search(r'\b(UTM\s*Y|Y\s*UTM|NORTHING)\b|\bY\b', cell_u):
                    if tmp_y == -1:
                        tmp_y = ci
                    continue

                # 6. Kolom Kode / Identifikasi Titik Kartometrik
                if any(kw in cell_u for kw in ["KODE", "TITIK", "IDENTIFIKASI", "ID TITIK", "NAMA TITIK", "VERTEKS", "POINT"]):
                    if tmp_kode == -1:
                        tmp_kode = ci
                    continue

            # Fallback untuk tmp_kode: jika belum terdeteksi dari kata kunci,
            # pilih kolom pertama yang belum terpakai oleh no, lat, lon, x, y
            if tmp_kode == -1:
                assigned = {c for c in [tmp_no, tmp_lat, tmp_lon, tmp_x, tmp_y] if c >= 0}
                for ci in range(len(row)):
                    if ci not in assigned:
                        tmp_kode = ci
                        break

            # Validasi baris header: minimal terdeteksi 2 kolom koordinat / kode
            n_signals = sum(1 for c in [tmp_kode, tmp_lat, tmp_lon, tmp_x, tmp_y] if c >= 0)
            if n_signals >= 2:
                header_row_idx = ri
                col_no, col_kode, col_lintang, col_bujur, col_x, col_y = tmp_no, tmp_kode, tmp_lat, tmp_lon, tmp_x, tmp_y
                logger.info(
                    f"Header kolom terdeteksi di baris {ri}: "
                    f"no={col_no}, kode={col_kode}, lat={col_lintang}, lon={col_bujur}, x={col_x}, y={col_y}"
                )
                break

        if header_row_idx < 0:
            logger.debug("Header kolom tidak ditemukan di tabel ini, skip.")
            continue

        # ── Ekstraksi baris data setelah header ──
        for ri, row in enumerate(tbl[header_row_idx + 1:], 1):
            if not row:
                continue

            def _cell(idx: int) -> str:
                if 0 <= idx < len(row):
                    v = str(row[idx] or "").strip().replace("\n", " ")
                    return "" if v in ("-", "None", "none", "N/A") else v
                return ""

            no_val = _cell(col_no) if col_no >= 0 else str(ri)
            kode = _cell(col_kode) if col_kode >= 0 else ""
            lintang = _cell(col_lintang) if col_lintang >= 0 else ""
            bujur = _cell(col_bujur) if col_bujur >= 0 else ""
            x = _cell(col_x) if col_x >= 0 else ""
            y = _cell(col_y) if col_y >= 0 else ""

            # Jika kode kosong tapi no_val ada dan koordinat tersedia, buat kode dari no_val
            if not kode and no_val:
                kode = f"TK-{no_val}"

            # Baris dinyatakan valid jika ada kode (atau no_val) DAN minimal satu nilai koordinat
            has_coords = bool(lintang or bujur or x or y)
            if not (kode or no_val) or not has_coords:
                continue

            rows_out.append({
                "no": no_val or str(ri),
                "kode": kode,
                "lintang": lintang,
                "bujur": bujur,
                "x": x,
                "y": y,
            })

        if rows_out:
            logger.info(f"Structured extraction dari tabel: {len(rows_out)} baris")
            break  # Hentikan setelah tabel kartometrik ditemukan

    return rows_out


def _build_final_rows(raw_rows: List[Dict]) -> List[Dict]:
    """Tambahkan nomor urut dan duplikasi key uppercase untuk kompatibilitas laporan."""
    final: List[Dict] = []
    for i, rec in enumerate(raw_rows, 1):
        no_str = rec.get("no") or str(i)
        final.append({
            "no": no_str,
            "kode": rec.get("kode", ""),
            "lintang": rec.get("lintang", ""),
            "bujur": rec.get("bujur", ""),
            "x": rec.get("x", ""),
            "y": rec.get("y", ""),
            # Standardized uppercase keys (untuk kompatibilitas laporan)
            "NO": no_str,
            "TITIK KARTOMETRIK": rec.get("kode", ""),
            "LINTANG": rec.get("lintang", ""),
            "BUJUR": rec.get("bujur", ""),
            "X(M)": rec.get("x", ""),
            "Y(M)": rec.get("y", ""),
        })
    return final


def _read_table_from_pdfplumber(file_bytes: bytes) -> Dict[str, Any]:
    """
    Ekstraksi tabel dari PDF digital menggunakan pdfplumber.

    Strategi 1 (Utama): Column-Aware Structured Extraction
      - Deteksi header kolom (KODE, LINTANG, BUJUR, X, Y) pada setiap halaman
      - Map setiap sel ke kolom yang benar
      - Jauh lebih andal daripada penggabungan buta

    Strategi 2 (Fallback): State Machine Text Parser
      - Jalankan classify_data_tokens_in_text + parse_with_state_machine
      - Digunakan hanya jika structured extraction gagal
    """
    try:
        import io
        import pdfplumber

        raw_text_parts: List[str] = []
        all_rows_structured: List[Dict] = []

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                pg_text = page.extract_text() or ""

                # Periksa apakah halaman ini mengandung tabel kartometrik
                is_kartometrik_page = bool(re.search(
                    r'(DAFTAR\s+TITIK\s+KARTOMETRIK|TITIK\s+KARTOMETRIK|DAFTAR\s+KOORDINAT|KOORDINAT\s+TITIK|DAFTAR\s+KOORDINAT\s+TITIK\s+BATAS|NOMOR\s+TITIK\s+BATAS)',
                    pg_text, re.IGNORECASE
                ))

                if not is_kartometrik_page:
                    continue

                raw_text_parts.append(pg_text)
                logger.info(f"Halaman kartometrik ditemukan ({len(pg_text)} karakter teks)")

                # Strategi 1: Structured column-aware extraction
                page_rows = _extract_structured_table_from_page(page)
                if page_rows:
                    all_rows_structured.extend(page_rows)

        raw_table_text = "\n".join(raw_text_parts)

        # ── Strategi 1 berhasil ──
        if all_rows_structured:
            final_rows = _build_final_rows(all_rows_structured)
            logger.info(f"pdfplumber Structured berhasil: {len(final_rows)} baris titik kartometrik.")
            return {
                "rows": final_rows,
                "raw_table_text": raw_table_text,
                "method": "OCR + Table Reader (pdfplumber + Kolom Terstruktur)",
                "error": None
            }

        # ── Strategi 2: Fallback State Machine ──
        if raw_table_text.strip():
            tokens = classify_data_tokens_in_text(raw_table_text)
            rows_sm = parse_with_state_machine(tokens)
            if rows_sm:
                logger.info(f"pdfplumber State Machine berhasil: {len(rows_sm)} baris titik kartometrik.")
                return {
                    "rows": rows_sm,
                    "raw_table_text": raw_table_text,
                    "method": "OCR + Table Reader (pdfplumber + State Machine)",
                    "error": None
                }

    except ImportError:
        logger.warning("pdfplumber tidak tersedia.")
    except Exception as e:
        logger.error(f"pdfplumber error: {e}", exc_info=True)

    return {"rows": [], "raw_table_text": "", "method": "", "error": "pdfplumber gagal"}


def extract_titik_kartometrik(
    file_bytes: Optional[bytes],
    filename: str,
    full_text: str,
    image_cv: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    """
    Entry point utama ekstraksi tabel titik kartometrik (Tahap 3 - Tahap 8).
    """
    import os
    ext = os.path.splitext(filename.lower())[1]

    # Strategi 1: PDF Digital (pdfplumber + State Machine)
    if ext == ".pdf" and file_bytes:
        pdf_res = _read_table_from_pdfplumber(file_bytes)
        if pdf_res["rows"]:
            return pdf_res

    # Strategi 2: Image / Visual Crop (Tahap 3 s.d. Tahap 8 Pipeline)
    crop_ocr_text = ""
    table_type = "unlined"

    if image_cv is not None:
        # Tahap 3 & 4: Deteksi Area & Crop Tabel
        crop_img, bbox, crop_ocr_text = detect_and_crop_table_area(image_cv, full_text)

        if crop_img is not None:
            # Tahap 5: Deteksi Struktur Tabel
            table_type = detect_table_structure(crop_img)

            # Tahap 6A vs 6B
            if table_type == "lined":
                cell_text = extract_table_cells_6a(crop_img)
                if cell_text:
                    crop_ocr_text = cell_text

    # Gunakan teks hasil crop (atau full_text sebagai fallback)
    target_text = crop_ocr_text if crop_ocr_text.strip() else full_text

    # Tahap 7: Identifikasi Jenis Data Token (Classifier)
    tokens = classify_data_tokens_in_text(target_text)

    # Tahap 8: State Machine Parser
    rows = parse_with_state_machine(tokens)

    method_str = f"OCR + State Machine ({'Crop Lined' if table_type == 'lined' else 'Crop Unlined'})"

    if rows:
        return {
            "rows": rows,
            "raw_table_text": target_text,
            "method": method_str,
            "error": None
        }

    return {
        "rows": [],
        "raw_table_text": target_text,
        "method": "OCR + Table Reader",
        "error": "Tidak ada data titik kartometrik yang berhasil diekstraksi."
    }
