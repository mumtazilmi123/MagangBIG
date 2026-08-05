"""
table_reader.py — Modul Ekstraksi Tabel Titik Kartometrik
==========================================================
Membaca tabel koordinat titik kartometrik dari:
1. PDF digital: menggunakan pdfplumber (lebih akurat)
2. Gambar (JPG/PNG): menggunakan pytesseract dalam mode tabel

Format tabel yang diharapkan:
  No | Kode Titik | Lintang (DMS/DD) | Bujur (DMS/DD) | X (UTM) | Y (UTM)

Mengembalikan:
{
  "rows": [ {no, kode, lintang, bujur, x, y} ],
  "raw_table_text": str,
  "method": str,
  "error": str atau None
}
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("peta_audit.table_reader")


def _parse_coordinate_value(raw: str) -> str:
    """Bersihkan dan normalisasi nilai koordinat."""
    if not raw:
        return ""
    # Hapus karakter non-relevan
    cleaned = re.sub(r'[^\d°\'".,\-\+LSUBTEWNlsub]', ' ', raw)
    return cleaned.strip()


def _parse_table_rows_from_text(text: str) -> List[Dict[str, str]]:
    """
    Parsing teks bebas untuk mencari pola baris tabel koordinat.
    Pola: angka (no) + kode titik + koordinat lintang + bujur [+ X + Y]
    """
    rows = []

    # Pattern baris tabel titik kartometrik
    # Contoh: "1  TK.001  6°30'00" LS  106°30'00" BT  692000  9280000"
    # Pattern lebih longgar:
    row_pattern = re.compile(
        r'(\d{1,3})'                          # Nomor urut
        r'[\s\t|]+([A-Za-z]{1,5}[\.\-]?\d+)' # Kode titik (TK.001, BT-01, dll)
        r'[\s\t|]+(.*?)'                       # Lintang
        r'[\s\t|]+(.*?)'                       # Bujur
        r'(?:[\s\t|]+([\d\.,]+))?'             # X (opsional)
        r'(?:[\s\t|]+([\d\.,]+))?',            # Y (opsional)
        re.IGNORECASE
    )

    # Coba ekstrak baris per baris
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue

        # Cek apakah mengandung angka nomor urut + koordinat
        m = re.match(r'^(\d{1,3})[\s\t|]+(\S+)[\s\t|]+(.+)', line)
        if not m:
            continue

        no = m.group(1)
        kode = m.group(2)
        rest = m.group(3)

        # Cari DMS atau DD dalam sisa baris
        dms_matches = re.findall(
            r'\d{1,3}[°\u00b0]\s*\d{1,2}[\'`\u2032]\s*\d{1,2}(?:[.,]\d+)?[\"\u2033]?\s*(?:LS|LU|BT|BB|S|N|E|W)?',
            rest, re.IGNORECASE
        )

        # Cari koordinat UTM (angka besar 6-7 digit)
        utm_matches = re.findall(r'\b(\d{5,7}(?:[.,]\d{0,3})?)\b', rest)

        row = {
            "no": no,
            "kode": kode,
            "lintang": dms_matches[0] if len(dms_matches) > 0 else "",
            "bujur": dms_matches[1] if len(dms_matches) > 1 else "",
            "x": utm_matches[0] if len(utm_matches) > 0 else "",
            "y": utm_matches[1] if len(utm_matches) > 1 else "",
        }

        # Hanya tambahkan jika ada minimal kode + lintang atau kode + x
        if kode and (row["lintang"] or row["x"]):
            rows.append(row)

    return rows


def _read_table_from_pdfplumber(file_bytes: bytes, page_index: int = 0) -> Dict[str, Any]:
    """
    Ekstraksi tabel dari PDF menggunakan pdfplumber.
    Lebih akurat dari OCR untuk PDF digital.
    """
    try:
        import io
        import pdfplumber

        rows_all = []
        raw_table_text = ""

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            # Cari tabel di semua halaman (tabel titik bisa di halaman terpisah)
            for pg_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for tbl in tables:
                    if not tbl:
                        continue

                    # Cek apakah tabel ini berisi koordinat
                    header_row = tbl[0] if tbl else []
                    header_text = " ".join([str(c).lower() for c in header_row if c])

                    is_coord_table = any(kw in header_text for kw in
                                         ["titik", "lintang", "bujur", "koordinat", "latitude", "longitude", "tk", "x", "y"])

                    if is_coord_table or len(rows_all) == 0:
                        for i, row in enumerate(tbl[1:], 1):  # Skip header
                            if not row or all(c is None or str(c).strip() == '' for c in row):
                                continue

                            cells = [str(c).strip() if c else "" for c in row]

                            # Mapping kolom (adaptif berdasarkan jumlah kolom)
                            row_dict = {"no": "", "kode": "", "lintang": "", "bujur": "", "x": "", "y": ""}

                            if len(cells) >= 6:
                                row_dict = {
                                    "no": cells[0],
                                    "kode": cells[1],
                                    "lintang": cells[2],
                                    "bujur": cells[3],
                                    "x": cells[4],
                                    "y": cells[5]
                                }
                            elif len(cells) >= 4:
                                row_dict = {
                                    "no": cells[0],
                                    "kode": cells[1],
                                    "lintang": cells[2],
                                    "bujur": cells[3],
                                    "x": cells[4] if len(cells) > 4 else "",
                                    "y": cells[5] if len(cells) > 5 else ""
                                }
                            elif len(cells) >= 2:
                                row_dict["no"] = cells[0]
                                row_dict["kode"] = cells[1]

                            # Validasi: pastikan ada data koordinat
                            has_data = any([
                                row_dict["lintang"],
                                row_dict["bujur"],
                                row_dict["x"],
                                row_dict["y"]
                            ])

                            if has_data:
                                rows_all.append(row_dict)
                                raw_table_text += " | ".join(cells) + "\n"

        if rows_all:
            logger.info(f"pdfplumber berhasil mengekstrak {len(rows_all)} baris tabel.")
            return {
                "rows": rows_all,
                "raw_table_text": raw_table_text,
                "method": "OCR + Table Reader (pdfplumber)",
                "error": None
            }

    except ImportError:
        logger.warning("pdfplumber tidak tersedia untuk ekstraksi tabel.")
    except Exception as e:
        logger.error(f"pdfplumber table extraction error: {e}")

    return {"rows": [], "raw_table_text": "", "method": "", "error": "pdfplumber gagal"}


def _read_table_from_ocr_text(full_text: str) -> Dict[str, Any]:
    """
    Fallback: parsing tabel dari teks OCR penuh.
    """
    rows = _parse_table_rows_from_text(full_text)
    if rows:
        return {
            "rows": rows,
            "raw_table_text": full_text,
            "method": "OCR + Rule Based (text parsing)",
            "error": None
        }
    return {"rows": [], "raw_table_text": "", "method": "OCR", "error": "Tidak ada baris tabel yang ditemukan"}


def extract_titik_kartometrik(
    file_bytes: Optional[bytes],
    filename: str,
    full_text: str
) -> Dict[str, Any]:
    """
    Entry point utama untuk ekstraksi tabel titik kartometrik.
    
    Strategi:
    1. Jika PDF: coba pdfplumber (paling akurat)
    2. Fallback: parsing teks OCR
    """
    import os
    ext = os.path.splitext(filename.lower())[1]

    # Strategi 1: PDF dengan pdfplumber
    if ext == ".pdf" and file_bytes:
        result = _read_table_from_pdfplumber(file_bytes)
        if result["rows"]:
            return result

    # Strategi 2: Parsing teks OCR (berlaku untuk semua format)
    if full_text:
        result = _read_table_from_ocr_text(full_text)
        if result["rows"]:
            return result

    # Tidak ada tabel ditemukan
    return {
        "rows": [],
        "raw_table_text": "",
        "method": "OCR + Table Reader",
        "error": "Tidak ada data titik kartometrik yang berhasil diekstraksi."
    }
