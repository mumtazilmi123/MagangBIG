"""
validator.py — Modul Rule-Based Validasi Komponen Peta Batas Desa
==================================================================
Memeriksa setiap komponen wajib Template BIG menggunakan:
- Pencarian keyword pada teks OCR (rule-based)
- Regex untuk pola terstruktur (skala angka, koordinat, dll)
- Integrasi hasil Computer Vision dari vision.py

Setiap fungsi check_* mengembalikan dict:
{
  "status":     "found" | "uncertain" | "not_found",
  "confidence": float (0.0 - 1.0),
  "method":     str (deskripsi metode yang digunakan),
  "evidence":   str (bukti deteksi),
  "value":      str (nilai yang diekstrak, jika ada),
  "bbox":       tuple atau None,
  "notes":      str (catatan/rekomendasi jika bermasalah)
}
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("peta_audit.validator")

# ─────────────────────────────────────────────────
# KONSTANTA KEYWORD
# ─────────────────────────────────────────────────

JUDUL_KEYWORDS = [
    "peta batas desa", "peta batas kelurahan", "peta batas wilayah",
    "peta administrasi", "peta desa", "peta batas", "batas desa",
    "batas kelurahan", "peta wilayah desa", "map", "peta"
]

DESA_KEYWORDS = ["desa", "kelurahan", "kel.", "ds."]
KECAMATAN_KEYWORDS = ["kecamatan", "kec.", "kec "]
KABUPATEN_KEYWORDS = ["kabupaten", "kota", "kab.", "kab "]
PROVINSI_KEYWORDS = ["provinsi", "prop.", "prov.", "province"]

PROYEKSI_KEYWORDS = [
    "transverse mercator", "universal transverse mercator", "utm",
    "mercator", "geographic", "lambert", "tm3", "tm 3", "proyeksi",
    "projection", "cylindrical"
]

SISTEM_GRID_KEYWORDS = [
    "utm", "grid utm", "sistem grid", "geographic", "wgs",
    "sistem koordinat", "koordinat geografis", "latlong", "lat/lon"
]

DATUM_KEYWORDS = [
    "srgi 2013", "srgi2013", "wgs 84", "wgs84", "dgn95", "id74",
    "datum", "horizontal datum", "spheroid", "ellipsoid", "grs80",
    "referensi geodesi"
]

LEGENDA_KEYWORDS = [
    "legenda", "legend", "keterangan", "simbol", "warna", "lambang"
]

SUMBER_DATA_KEYWORDS = [
    "sumber data", "sumber peta", "sumber", "source", "data bps",
    "citra satelit", "peta rbi", "big", "bakosurtanal", "foto udara",
    "dijitasi", "digitasi", "lapangan", "survei", "bpn", "atrbpn"
]

PENERBIT_KEYWORDS = [
    "dibuat oleh", "diperiksa oleh", "disetujui oleh", "kepala desa",
    "lurah", "camat", "bupati", "walikota", "kantor", "dinas",
    "pemerintah desa", "pemerintah kota", "pemerintah kabupaten",
    "tanggal", "tahun", "nip", "ttd", "ditandatangani"
]

UTARA_KEYWORDS = ["utara", "north", r"\bN\b", "arah utara", "kompas"]

TITIK_KARTOMETRIK_KEYWORDS = [
    "titik kartometrik", "tk.", "titik batas", "batas desa",
    "koordinat titik", "daftar koordinat", "koordinat batas",
    "titik ikat", "titik kontrol", "boundary point"
]


# ─────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────

def _search_keywords(text: str, keywords: List[str], case_insensitive: bool = True) -> Tuple[bool, str]:
    """
    Cari keyword dalam teks. Kembalikan (found: bool, matched_keyword: str).
    """
    flags = re.IGNORECASE if case_insensitive else 0
    text_norm = text.replace("\n", " ").replace("\r", " ")
    for kw in keywords:
        try:
            if re.search(kw, text_norm, flags):
                # Ekstrak konteks 60 karakter di sekitar keyword
                m = re.search(kw, text_norm, flags)
                if m:
                    start = max(0, m.start() - 30)
                    end = min(len(text_norm), m.end() + 30)
                    ctx = text_norm[start:end].strip()
                    return True, f'"{ctx}"'
        except re.error:
            if kw.lower() in text_norm.lower():
                return True, kw
    return False, ""


def _make_result(status, confidence, method, evidence, value="", bbox=None, notes=""):
    return {
        "status": status,
        "confidence": round(float(confidence), 2),
        "method": method,
        "evidence": evidence,
        "value": value,
        "bbox": list(bbox) if bbox else None,
        "notes": notes
    }


# ─────────────────────────────────────────────────
# CHECKER FUNCTIONS
# ─────────────────────────────────────────────────

def check_judul_peta(text: str) -> Dict[str, Any]:
    """Komponen 1: Judul Peta."""
    found, ctx = _search_keywords(text, JUDUL_KEYWORDS)
    if found:
        # Coba ekstrak judul (baris yang mengandung keyword judul)
        lines = text.split("\n")
        for line in lines[:20]:  # Judul biasanya di atas
            line_s = line.strip()
            if any(kw.lower() in line_s.lower() for kw in ["peta batas", "peta desa", "peta wilayah", "peta administrasi"]):
                return _make_result(
                    "found", 0.90, "OCR + Rule Based",
                    f"OCR membaca: {ctx}",
                    line_s
                )
        return _make_result("found", 0.75, "OCR + Rule Based", f"OCR membaca: {ctx}", "Terdeteksi")
    return _make_result("not_found", 0.10, "OCR + Rule Based", "-", "",
                        notes="Judul peta tidak ditemukan. Tambahkan judul yang mengandung kata 'Peta Batas Desa'.")


def check_identitas_desa(text: str) -> Dict[str, Any]:
    """Komponen 2a: Desa/Kelurahan."""
    found, ctx = _search_keywords(text, DESA_KEYWORDS)
    if found:
        # Coba ekstrak nama desa
        m = re.search(r'(?:desa|kelurahan|kel\.|ds\.)\s*[:\-]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
        val = m.group(1).strip()[:50] if m else "Terdeteksi"
        return _make_result("found", 0.82, "OCR + Rule Based", f"OCR membaca: {ctx}", val)
    return _make_result("not_found", 0.10, "OCR + Rule Based", "-", "",
                        notes="Identitas Desa/Kelurahan tidak ditemukan.")


def check_identitas_kecamatan(text: str) -> Dict[str, Any]:
    """Komponen 2b: Kecamatan."""
    found, ctx = _search_keywords(text, KECAMATAN_KEYWORDS)
    if found:
        m = re.search(r'(?:kecamatan|kec\.?)\s*[:\-]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
        val = m.group(1).strip()[:50] if m else "Terdeteksi"
        return _make_result("found", 0.82, "OCR + Rule Based", f"OCR membaca: {ctx}", val)
    return _make_result("not_found", 0.10, "OCR + Rule Based", "-", "",
                        notes="Identitas Kecamatan tidak ditemukan.")


def check_identitas_kabupaten(text: str) -> Dict[str, Any]:
    """Komponen 2c: Kabupaten/Kota."""
    found, ctx = _search_keywords(text, KABUPATEN_KEYWORDS)
    if found:
        m = re.search(r'(?:kabupaten|kota|kab\.?)\s*[:\-]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
        val = m.group(1).strip()[:50] if m else "Terdeteksi"
        return _make_result("found", 0.82, "OCR + Rule Based", f"OCR membaca: {ctx}", val)
    return _make_result("not_found", 0.10, "OCR + Rule Based", "-", "",
                        notes="Identitas Kabupaten/Kota tidak ditemukan.")


def check_identitas_provinsi(text: str) -> Dict[str, Any]:
    """Komponen 2d: Provinsi."""
    found, ctx = _search_keywords(text, PROVINSI_KEYWORDS)
    if found:
        m = re.search(r'(?:provinsi|prop\.|prov\.?)\s*[:\-]?\s*([A-Za-z\s]+)', text, re.IGNORECASE)
        val = m.group(1).strip()[:50] if m else "Terdeteksi"
        return _make_result("found", 0.82, "OCR + Rule Based", f"OCR membaca: {ctx}", val)
    return _make_result("not_found", 0.10, "OCR + Rule Based", "-", "",
                        notes="Identitas Provinsi tidak ditemukan.")


def check_skala_angka(text: str) -> Dict[str, Any]:
    """Komponen 3a: Skala Angka (contoh: 1:5000, 1 : 50.000)."""
    # Pattern skala angka: 1 : 5000 atau 1:50.000 atau 1 : 50,000
    pattern = r'1\s*[:：]\s*[\d\.,\s]+'
    m = re.search(pattern, text)
    if m:
        raw = m.group(0).strip()
        # Bersihkan
        val = re.sub(r'[\s]', '', raw)
        return _make_result("found", 0.92, "OCR + Regex", f'OCR membaca: "{raw}"', val)
    return _make_result("not_found", 0.10, "OCR + Regex", "-", "",
                        notes="Skala angka (misal 1:5000) tidak ditemukan dalam teks.")


def check_skala_grafis(text: str, vision_result: Optional[Dict] = None) -> Dict[str, Any]:
    """Komponen 3b: Skala Grafis (bar scale)."""
    # Cek dari vision
    if vision_result and vision_result.get("detected"):
        return _make_result(
            "found",
            vision_result["confidence"],
            "Computer Vision",
            vision_result["evidence"],
            "Terdeteksi (visual)"
        )

    # Cek dari teks: keyword skala grafis atau satuan jarak
    patterns = [
        r'\d+\s*(?:m|meter|km|kilometer)',
        r'skala\s+grafis',
        r'skala\s+batang',
        r'\b0\s+\d+\s+(?:\d+\s+)?(?:m|km)\b'
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return _make_result("found", 0.65, "OCR + Rule Based",
                                f'OCR membaca: "{m.group(0)}"', m.group(0))

    return _make_result("uncertain", 0.20, "Computer Vision + OCR",
                        "Skala grafis tidak terdeteksi secara visual maupun teks",
                        notes="Skala grafis tidak ditemukan. Tambahkan bar scale pada peta.")


def check_arah_utara(text: str, vision_result: Optional[Dict] = None) -> Dict[str, Any]:
    """Komponen 4: Arah Utara."""
    # Cek dari vision
    if vision_result and vision_result.get("detected"):
        conf = vision_result["confidence"]
        status = "found" if conf >= 0.5 else "uncertain"
        return _make_result(status, conf, "Computer Vision", vision_result["evidence"])

    # Cek teks: huruf N terisolasi atau kata "utara"
    found, ctx = _search_keywords(text, UTARA_KEYWORDS)
    if found:
        return _make_result("uncertain", 0.45, "OCR + Rule Based",
                            f'OCR membaca: {ctx}',
                            notes="Kata 'utara/N' ditemukan dalam teks, namun simbol panah utara perlu dikonfirmasi visual.")

    return _make_result("not_found", 0.10, "Computer Vision + OCR", "-",
                        notes="Simbol arah utara tidak terdeteksi. Tambahkan tanda panah utara pada peta.")


def check_grid_koordinat(text: str, layout_result: Optional[Dict] = None) -> Dict[str, Any]:
    """Komponen 5: Grid Koordinat."""
    if layout_result:
        if layout_result.get("has_grid"):
            h_lines = layout_result.get("h_lines", 0)
            v_lines = layout_result.get("v_lines", 0)
            conf = layout_result.get("confidence", 0.5)
            return _make_result("found", conf, "Computer Vision",
                                f"Grid berhasil dideteksi: {h_lines} garis horizontal, {v_lines} garis vertikal")
        elif layout_result.get("h_lines", 0) > 0 or layout_result.get("v_lines", 0) > 0:
            return _make_result("uncertain", 0.35, "Computer Vision",
                                f"Grid hanya terdeteksi sebagian (H={layout_result.get('h_lines',0)}, V={layout_result.get('v_lines',0)})",
                                notes="Grid koordinat hanya terdeteksi sebagian. Pastikan grid menyeluruh pada seluruh area peta.")

    # Fallback: cek teks grid
    grid_patterns = [r'\bgrid\b', r'graticule', r'jaring', r'koordinat grid']
    found, ctx = _search_keywords(text, grid_patterns)
    if found:
        return _make_result("uncertain", 0.40, "OCR + Rule Based",
                            f"OCR membaca: {ctx}",
                            notes="Kata 'grid' ditemukan, namun keberadaan visual grid perlu dikonfirmasi.")

    return _make_result("not_found", 0.10, "Computer Vision + OCR", "-",
                        notes="Grid koordinat tidak terdeteksi. Tambahkan grid pada body peta.")


def check_label_koordinat(text: str) -> Dict[str, Any]:
    """Komponen 6: Label Koordinat (nilai koordinat pada tepi peta)."""
    # Cari pola koordinat: derajat-menit-detik atau desimal
    # DMS: 106°30'00" BT atau 6°30'00" LS
    dms_pattern = r'\d{1,3}[°\u00b0]\s*\d{1,2}[\'`\u2032]\s*\d{1,2}(?:[.,]\d+)?[\"\u2033]?\s*(?:LS|LU|BT|BB|S|N|E|W)?'
    dd_pattern = r'\d{1,3}[.,]\d{2,6}°?'

    m = re.search(dms_pattern, text, re.IGNORECASE)
    if m:
        return _make_result("found", 0.88, "OCR + Regex",
                            f'OCR membaca koordinat DMS: "{m.group(0)}"',
                            m.group(0))

    # Cari koordinat desimal
    matches = re.findall(dd_pattern, text)
    geo_matches = [x for x in matches if re.search(r'(?:1[0-5][0-9]|[0-9]{1,2})[.,]\d+', x)]
    if len(geo_matches) >= 2:
        return _make_result("found", 0.75, "OCR + Regex",
                            f"OCR menemukan {len(geo_matches)} nilai koordinat desimal: {', '.join(geo_matches[:3])}",
                            ", ".join(geo_matches[:3]))

    # Cari label aksial (N, S, E, W atau angka besar yang tampak koordinat)
    utm_pattern = r'\d{5,7}\s*(?:m|mT|mU)'
    m2 = re.search(utm_pattern, text)
    if m2:
        return _make_result("found", 0.70, "OCR + Regex",
                            f'OCR membaca label UTM: "{m2.group(0)}"', m2.group(0))

    return _make_result("not_found", 0.10, "OCR + Regex", "-",
                        notes="Label koordinat tidak ditemukan. Pastikan nilai koordinat tertera pada tepi peta.")


def check_sistem_proyeksi(text: str) -> Dict[str, Any]:
    """Komponen 7: Sistem Proyeksi."""
    found, ctx = _search_keywords(text, PROYEKSI_KEYWORDS)
    if found:
        # Ekstrak nilai proyeksi
        proj_val = ""
        for kw in ["transverse mercator", "utm", "mercator", "geographic", "lambert"]:
            if kw.lower() in text.lower():
                proj_val = kw.upper()
                break
        return _make_result("found", 0.87, "OCR + Rule Based",
                            f"OCR membaca: {ctx}", proj_val)

    return _make_result("not_found", 0.10, "OCR + Rule Based", "-",
                        notes="Sistem proyeksi tidak ditemukan. Tambahkan keterangan proyeksi (misal: Transverse Mercator).")


def check_sistem_grid(text: str) -> Dict[str, Any]:
    """Komponen 8: Sistem Grid."""
    found, ctx = _search_keywords(text, SISTEM_GRID_KEYWORDS)
    if found:
        return _make_result("found", 0.80, "OCR + Rule Based", f"OCR membaca: {ctx}", "Terdeteksi")
    return _make_result("not_found", 0.10, "OCR + Rule Based", "-",
                        notes="Sistem grid tidak ditemukan. Tambahkan keterangan sistem grid (misal: UTM Zone 49S).")


def check_datum_horizontal(text: str) -> Dict[str, Any]:
    """Komponen 9: Datum Horizontal."""
    found, ctx = _search_keywords(text, DATUM_KEYWORDS)
    if found:
        # Identifikasi datum
        datum_val = ""
        for datum in ["SRGI 2013", "WGS 84", "WGS84", "DGN95", "ID74"]:
            if datum.lower() in text.lower():
                datum_val = datum
                break
        return _make_result("found", 0.90, "OCR + Rule Based",
                            f"OCR membaca: {ctx}", datum_val or "Terdeteksi")

    return _make_result("not_found", 0.10, "OCR + Rule Based", "-",
                        notes="Datum horizontal tidak ditemukan. Tambahkan keterangan datum (misal: SRGI 2013).")


def check_legenda(text: str, vision_result: Optional[Dict] = None) -> Dict[str, Any]:
    """Komponen 10: Legenda."""
    # Cek visual
    if vision_result and vision_result.get("detected"):
        conf = vision_result["confidence"]
        status = "found" if conf >= 0.45 else "uncertain"
        return _make_result(status, conf, "Computer Vision + OCR", vision_result["evidence"])

    # Cek teks
    found, ctx = _search_keywords(text, LEGENDA_KEYWORDS)
    if found:
        return _make_result("found", 0.75, "OCR + Rule Based",
                            f"OCR membaca: {ctx}",
                            "Ditemukan dalam teks")

    return _make_result("not_found", 0.10, "Computer Vision + OCR", "-",
                        notes="Legenda tidak ditemukan. Tambahkan legenda peta.")


def check_inset_lokasi(text: str, vision_result: Optional[Dict] = None) -> Dict[str, Any]:
    """Komponen 11: Inset Lokasi."""
    if vision_result and vision_result.get("detected"):
        conf = vision_result["confidence"]
        status = "found" if conf >= 0.45 else "uncertain"
        return _make_result(status, conf, "Computer Vision", vision_result["evidence"])

    # Cek teks
    inset_kw = ["inset", "lokasi", "peta acuan", "peta induk", "peta mini", "overview"]
    found, ctx = _search_keywords(text, inset_kw)
    if found:
        return _make_result("uncertain", 0.45, "OCR + Rule Based",
                            f"OCR membaca: {ctx}",
                            notes="Kata inset/lokasi ditemukan, namun visualnya perlu dikonfirmasi.")

    return _make_result("not_found", 0.10, "Computer Vision + OCR", "-",
                        notes="Inset lokasi tidak ditemukan. Tambahkan peta mini penunjuk lokasi.")


def check_sumber_data(text: str) -> Dict[str, Any]:
    """Komponen 12: Sumber Data."""
    found, ctx = _search_keywords(text, SUMBER_DATA_KEYWORDS)
    if found:
        # Ekstrak sumber data
        m = re.search(r'sumber\s*(?:data|peta)?\s*[:\-]?\s*(.{10,80})', text, re.IGNORECASE)
        val = m.group(1).strip()[:80] if m else "Terdeteksi"
        return _make_result("found", 0.85, "OCR + Rule Based", f"OCR membaca: {ctx}", val)

    return _make_result("not_found", 0.10, "OCR + Rule Based", "-",
                        notes="Sumber data tidak ditemukan. Tambahkan keterangan sumber data peta.")


def check_titik_kartometrik(text: str, table_result: Optional[Dict] = None) -> Dict[str, Any]:
    """Komponen 13: Daftar Titik Kartometrik."""
    # Cek dari tabel yang diekstrak
    if table_result and table_result.get("rows"):
        n = len(table_result["rows"])
        return _make_result("found", 0.90, "OCR + Table Reader",
                            f"OCR + Table Reader berhasil membaca {n} titik kartometrik",
                            f"{n} Titik")

    # Cek teks
    found, ctx = _search_keywords(text, TITIK_KARTOMETRIK_KEYWORDS)
    if found:
        # Cari angka jumlah titik
        m = re.search(r'(\d+)\s*(?:titik|batas|koordinat)', text, re.IGNORECASE)
        val = f"{m.group(1)} Titik" if m else "Terdeteksi"
        return _make_result("found", 0.70, "OCR + Rule Based", f"OCR membaca: {ctx}", val)

    return _make_result("not_found", 0.10, "OCR + Table Reader", "-",
                        notes="Daftar titik kartometrik tidak ditemukan.")


def check_batas_administrasi(text: str, vision_result: Optional[Dict] = None) -> Dict[str, Any]:
    """Komponen 14: Batas Administrasi."""
    if vision_result and vision_result.get("detected"):
        conf = vision_result["confidence"]
        status = "found" if conf >= 0.4 else "uncertain"
        return _make_result(status, conf, "Computer Vision", vision_result["evidence"])

    # Cek teks
    batas_kw = ["batas administrasi", "batas desa", "batas kecamatan",
                "batas kabupaten", "batas provinsi", "batas wilayah"]
    found, ctx = _search_keywords(text, batas_kw)
    if found:
        return _make_result("uncertain", 0.50, "OCR + Rule Based",
                            f"OCR membaca: {ctx}",
                            notes="Batas administrasi disebut dalam teks, namun visualnya perlu dikonfirmasi.")

    return _make_result("not_found", 0.10, "Computer Vision + OCR", "-",
                        notes="Batas administrasi tidak terdeteksi. Pastikan garis batas wilayah tergambar jelas.")


def check_informasi_penerbit(text: str) -> Dict[str, Any]:
    """Komponen 16: Informasi Penerbit."""
    found, ctx = _search_keywords(text, PENERBIT_KEYWORDS)
    if found:
        # Cari tahun
        year_m = re.search(r'\b(20[0-2][0-9])\b', text)
        year_val = year_m.group(1) if year_m else ""
        val = f"Tahun: {year_val}" if year_val else "Terdeteksi"
        return _make_result("found", 0.82, "OCR + Rule Based",
                            f"OCR membaca: {ctx}", val)

    return _make_result("not_found", 0.10, "OCR + Rule Based", "-",
                        notes="Informasi penerbit tidak ditemukan. Tambahkan nama penerbit, penandatangan, dan tanggal.")
