"""
report.py — Modul Generate Laporan Audit Peta Batas Desa
=========================================================
Mengumpulkan semua hasil deteksi komponen dan menghasilkan
JSON audit lengkap untuk dikonsumsi oleh frontend dashboard.

Struktur JSON output:
{
  "filename": str,
  "audit_timestamp": str,
  "audit_status": "LAYAK" | "PERLU_PERBAIKAN" | "TIDAK_SESUAI",
  "completeness_percent": float,
  "found_count": int,
  "not_found_count": int,
  "uncertain_count": int,
  "avg_confidence": float,
  "total_components": int,
  "components": [ { komponen per-baris } ],
  "titik_kartometrik": { rows, method, error },
  "summary": str
}
"""

import datetime
import logging
from typing import Dict, Any, List

logger = logging.getLogger("peta_audit.report")

# Nama komponen resmi sesuai spesifikasi
COMPONENT_NAMES = {
    "judul_peta":             "Judul Peta",
    "identitas_desa":         "Identitas Wilayah — Desa/Kelurahan",
    "identitas_kecamatan":    "Identitas Wilayah — Kecamatan",
    "identitas_kabupaten":    "Identitas Wilayah — Kabupaten/Kota",
    "identitas_provinsi":     "Identitas Wilayah — Provinsi",
    "skala_angka":            "Skala Angka",
    "skala_grafis":           "Skala Grafis",
    "arah_utara":             "Arah Utara",
    "label_koordinat":        "Label Koordinat",
    "sistem_proyeksi":        "Sistem Proyeksi",
    "sistem_grid":            "Sistem Grid",
    "datum_horizontal":       "Datum Horizontal",
    "legenda":                "Legenda",
    "inset_lokasi":           "Inset Lokasi",
    "sumber_data":            "Sumber Data",
    "titik_kartometrik":      "Daftar Titik Kartometrik",
    "batas_administrasi":     "Batas Administrasi",
    "informasi_penerbit":     "Informasi Penerbit",
}

# Komponen yang bersifat opsional (tidak mempengaruhi status LAYAK)
OPTIONAL_COMPONENTS = set()

# Urutan tampilan di dashboard
DISPLAY_ORDER = [
    "judul_peta",
    "identitas_desa",
    "identitas_kecamatan",
    "identitas_kabupaten",
    "identitas_provinsi",
    "skala_angka",
    "skala_grafis",
    "arah_utara",
    "label_koordinat",
    "sistem_proyeksi",
    "sistem_grid",
    "datum_horizontal",
    "legenda",
    "inset_lokasi",
    "sumber_data",
    "titik_kartometrik",
    "batas_administrasi",
    "informasi_penerbit",
]


def _status_label(status: str) -> str:
    mapping = {
        "found": "✓ Ditemukan",
        "uncertain": "⚠ Tidak Dapat Dipastikan",
        "not_found": "✗ Tidak Ditemukan"
    }
    return mapping.get(status, status)


def build_report(
    filename: str,
    component_results: Dict[str, Dict],
    titik_kartometrik_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Bangun laporan audit JSON dari semua hasil komponen.
    
    Args:
        filename: Nama file asli
        component_results: Dict {key: {status, confidence, method, evidence, value, bbox, notes}}
        titik_kartometrik_result: Result dari table_reader
    
    Returns:
        Dict JSON lengkap untuk frontend
    """
    # Hitung statistik
    mandatory_keys = [k for k in DISPLAY_ORDER if k not in OPTIONAL_COMPONENTS]
    all_keys = DISPLAY_ORDER

    found_count = 0
    not_found_count = 0
    uncertain_count = 0
    mandatory_found = 0
    mandatory_not_found = 0
    total_confidence = 0.0
    n_confidence = 0

    components_list = []
    for idx, key in enumerate(DISPLAY_ORDER, 1):
        result = component_results.get(key, {
            "status": "not_found",
            "confidence": 0.0,
            "method": "-",
            "evidence": "-",
            "value": "",
            "bbox": None,
            "notes": "Komponen tidak diperiksa."
        })

        status = result.get("status", "not_found")
        confidence = result.get("confidence", 0.0)
        is_optional = key in OPTIONAL_COMPONENTS

        if status == "found":
            found_count += 1
            if key in mandatory_keys:
                mandatory_found += 1
        elif status == "not_found":
            not_found_count += 1
            if key in mandatory_keys:
                mandatory_not_found += 1
        else:  # uncertain
            uncertain_count += 1

        total_confidence += confidence
        n_confidence += 1

        components_list.append({
            "no": idx,
            "key": key,
            "name": COMPONENT_NAMES.get(key, key),
            "is_optional": is_optional,
            "status": status,
            "status_label": _status_label(status),
            "confidence": confidence,
            "method": result.get("method", "-"),
            "evidence": result.get("evidence", "-"),
            "value": result.get("value", ""),
            "bbox": result.get("bbox"),
            "notes": result.get("notes", "")
        })

    # Hitung persentase kelengkapan (hanya komponen wajib)
    total_mandatory = len(mandatory_keys)
    completeness = round((mandatory_found / total_mandatory * 100), 1) if total_mandatory > 0 else 0.0
    avg_confidence = round(total_confidence / n_confidence, 2) if n_confidence > 0 else 0.0

    # Tentukan status audit
    # LAYAK: semua komponen wajib ditemukan (uncertain dianggap partial)
    # PERLU PERBAIKAN: sebagian komponen wajib tidak ditemukan (< 30% tidak ditemukan)
    # TIDAK SESUAI: lebih dari 40% komponen wajib tidak ditemukan
    if mandatory_not_found == 0:
        audit_status = "LAYAK"
        status_label = "✓ LAYAK"
        status_color = "green"
    elif mandatory_not_found <= int(total_mandatory * 0.35):
        audit_status = "PERLU_PERBAIKAN"
        status_label = "⚠ PERLU PERBAIKAN"
        status_color = "yellow"
    else:
        audit_status = "TIDAK_SESUAI"
        status_label = "✗ TIDAK SESUAI"
        status_color = "red"

    # Summary teks
    summary_lines = []
    if audit_status == "LAYAK":
        summary_lines.append("Peta telah memenuhi seluruh komponen wajib Template BIG.")
    else:
        missing = [c["name"] for c in components_list
                   if c["status"] == "not_found" and not c["is_optional"]]
        if missing:
            summary_lines.append(f"Komponen wajib tidak ditemukan ({len(missing)}):")
            for m in missing[:5]:
                summary_lines.append(f"  - {m}")
            if len(missing) > 5:
                summary_lines.append(f"  ... dan {len(missing)-5} lainnya.")

    timestamp = datetime.datetime.now().isoformat()

    return {
        "filename": filename,
        "audit_timestamp": timestamp,
        "audit_status": audit_status,
        "audit_status_label": status_label,
        "audit_status_color": status_color,
        "completeness_percent": completeness,
        "found_count": found_count,
        "not_found_count": not_found_count,
        "uncertain_count": uncertain_count,
        "avg_confidence": avg_confidence,
        "total_components": len(DISPLAY_ORDER),
        "mandatory_count": total_mandatory,
        "mandatory_found": mandatory_found,
        "components": components_list,
        "titik_kartometrik": {
            "rows": titik_kartometrik_result.get("rows", []),
            "method": titik_kartometrik_result.get("method", ""),
            "error": titik_kartometrik_result.get("error", ""),
            "total": len(titik_kartometrik_result.get("rows", []))
        },
        "summary": "\n".join(summary_lines) if summary_lines else "Audit selesai."
    }
