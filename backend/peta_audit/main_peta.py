"""
main_peta.py — FastAPI App Audit Peta Batas Desa
=================================================
Entry point server audit peta batas desa.
Berjalan di port 8001 (terpisah dari Veridoc SKVT di port 8000).

Endpoints:
  POST /api/peta/audit  — Upload file peta, terima JSON audit hasil
  GET  /api/peta/health — Health check
"""

import os
import sys
import logging
import traceback
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Tambahkan root backend ke sys.path agar import modul lama tetap bisa
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from peta_audit.modules.preprocessing import load_image_file
from peta_audit.modules.ocr import extract_full_text, extract_text_regions
from peta_audit.modules.layout import detect_regions_heuristic, detect_border_boxes
from peta_audit.modules.vision import (
    detect_north_arrow,
    detect_scale_bar,
    detect_inset_map,
    detect_boundary_lines,
    detect_legend_visually
)
from peta_audit.modules.validator import (
    check_judul_peta,
    check_identitas_desa,
    check_identitas_kecamatan,
    check_identitas_kabupaten,
    check_identitas_provinsi,
    check_skala_angka,
    check_skala_grafis,
    check_arah_utara,
    check_label_koordinat,
    check_sistem_proyeksi,
    check_sistem_grid,
    check_datum_horizontal,
    check_legenda,
    check_inset_lokasi,
    check_sumber_data,
    check_titik_kartometrik,
    check_batas_administrasi,
    check_informasi_penerbit,
)
from peta_audit.modules.table_reader import extract_titik_kartometrik
from peta_audit.modules.report import build_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("peta_audit_api")

# ─────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────

app = FastAPI(
    title="Audit Peta Batas Desa — Template BIG",
    description="API Audit komponen wajib Peta Batas Desa sesuai Template BIG. "
                "Mendukung file PDF (.pdf).",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────
# Batas ukuran file
# ─────────────────────────────────────────────────
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf"}


def _validate_file(file: UploadFile) -> None:
    ext = os.path.splitext((file.filename or "").lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format file tidak didukung: '{ext}'. Hanya berkas format PDF (.pdf) yang diterima."
        )


# ─────────────────────────────────────────────────
# Core Audit Pipeline
# ─────────────────────────────────────────────────

def run_audit_pipeline(file_bytes: bytes, filename: str) -> dict:
    """
    Menjalankan pipeline audit lengkap:
    1. Preprocessing
    2. OCR
    3. Layout Detection
    4. Computer Vision
    5. Validasi komponen (rule-based)
    6. Ekstraksi tabel titik kartometrik
    7. Generate laporan JSON
    """
    logger.info(f"=== Memulai audit: {filename} ({len(file_bytes)} bytes) ===")

    # ── 1. Preprocessing ──────────────────────────
    logger.info("Langkah 1: Preprocessing...")
    prep = load_image_file(file_bytes, filename)

    if prep.get("error") and not prep.get("image_cv") is not None:
        # Error fatal
        if prep["image_pil"] is None and prep["image_cv"] is None:
            raise ValueError(f"Gagal memuat file: {prep['error']}")

    image_pil = prep.get("image_pil")
    image_cv  = prep.get("image_cv")
    raw_text_pdf = prep.get("raw_text", "")

    has_visual = image_cv is not None

    # ── 2. OCR ────────────────────────────────────
    logger.info("Langkah 2: OCR...")
    if has_visual and image_pil is not None:
        full_text = extract_full_text(image_pil, image_cv, raw_text_pdf)
    else:
        full_text = raw_text_pdf  # Hanya teks vektor PDF

    logger.info(f"Total teks: {len(full_text)} karakter")

    # ── 3. Layout Detection ───────────────────────
    logger.info("Langkah 3: Deteksi layout...")
    boxes = []

    if has_visual and image_cv is not None:
        boxes = detect_border_boxes(image_cv)

    # ── 4. Computer Vision ────────────────────────
    logger.info("Langkah 4: Computer Vision...")
    vision_north   = detect_north_arrow(image_cv, full_text) if has_visual else {}
    vision_scale   = detect_scale_bar(image_cv)              if has_visual else {}
    vision_inset   = detect_inset_map(image_cv, full_text)   if has_visual else {}
    vision_boundary= detect_boundary_lines(image_cv)         if has_visual else {}
    vision_legend  = detect_legend_visually(image_cv)        if has_visual else {}

    # ── 5. Ekstraksi Titik Kartometrik ────────────
    logger.info("Langkah 5: Ekstraksi tabel titik kartometrik...")
    titik_result = extract_titik_kartometrik(file_bytes, filename, full_text, image_cv)

    # ── 6. Validasi Komponen ──────────────────────
    logger.info("Langkah 6: Validasi komponen...")
    component_results = {
        "judul_peta":          check_judul_peta(full_text),
        "identitas_desa":      check_identitas_desa(full_text),
        "identitas_kecamatan": check_identitas_kecamatan(full_text),
        "identitas_kabupaten": check_identitas_kabupaten(full_text),
        "identitas_provinsi":  check_identitas_provinsi(full_text),
        "skala_angka":         check_skala_angka(full_text),
        "skala_grafis":        check_skala_grafis(full_text, vision_scale),
        "arah_utara":          check_arah_utara(full_text, vision_north),
        "label_koordinat":     check_label_koordinat(full_text),
        "sistem_proyeksi":     check_sistem_proyeksi(full_text),
        "sistem_grid":         check_sistem_grid(full_text),
        "datum_horizontal":    check_datum_horizontal(full_text),
        "legenda":             check_legenda(full_text, vision_legend),
        "inset_lokasi":        check_inset_lokasi(full_text, vision_inset),
        "sumber_data":         check_sumber_data(full_text),
        "titik_kartometrik":   check_titik_kartometrik(full_text, titik_result),
        "batas_administrasi":  check_batas_administrasi(full_text, vision_boundary),
        "informasi_penerbit":  check_informasi_penerbit(full_text),
    }

    # ── 7. Generate Report ────────────────────────
    logger.info("Langkah 7: Generate laporan...")
    report = build_report(filename, component_results, titik_result)
    report["has_visual"] = has_visual
    report["page_count"] = prep.get("page_count", 1)

    logger.info(f"=== Audit selesai: {report['audit_status']} ({report['completeness_percent']}%) ===")
    return report


# ─────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────

@app.post("/api/peta/audit")
async def audit_peta(file: UploadFile = File(...)):
    """
    Audit file Peta Batas Desa.
    Terima file PDF/JPG/JPEG/PNG/TIFF.
    Kembalikan JSON hasil audit lengkap.
    """
    _validate_file(file)

    try:
        content = await file.read()

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File kosong (0 bytes).")

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Ukuran file ({len(content)//1024//1024} MB) melebihi batas 50 MB."
            )

        logger.info(f"File diterima: {file.filename} ({len(content)} bytes)")
        result = run_audit_pipeline(content, file.filename or "unknown")
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"ValueError: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan internal: {str(e)}")


@app.get("/api/peta/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": "Audit Peta Batas Desa",
        "version": "1.0.0",
        "description": "API Audit Komponen Peta BIG Template"
    }


# ─────────────────────────────────────────────────
# Mount Frontend Static Files
# ─────────────────────────────────────────────────
_frontend_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "peta_batas_desa"
)
if os.path.isdir(_frontend_path):
    app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend_peta")
    logger.info(f"Frontend tersedia di: {_frontend_path}")
else:
    logger.warning(f"Direktori frontend tidak ditemukan: {_frontend_path}")
