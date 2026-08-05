from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import re
import json
import logging
import traceback
from typing import Optional, List, Dict, Any

from audit_engine import process_audit_document, generate_consolidated_batch_pdf_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("veridoc_api")

app = FastAPI(
    title="Veridoc - Sistem Periksa & Audit Dokumen SKVT BIG",
    description="API Veridoc v5.5 - Audit 9 Catatan Kritis, Halaman PDF, Evaluasi RMSE Geomatika & Exporter GIS Multi-Format",
    version="5.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/audit")
async def audit_pdf(
    files: List[UploadFile] = File(...),
    utm_zone: str = Form("Auto"),
    datum: str = Form("EPSG:4326"),
    output_dir: Optional[str] = Form(None)
):
    """Audit satu atau banyak file PDF SKVT sekaligus."""
    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith('.pdf')]
    
    if not pdf_files:
        raise HTTPException(status_code=400, detail="Tidak ada file PDF yang valid diunggah.")
    
    # --- SINGLE FILE MODE ---
    if len(pdf_files) == 1:
        file = pdf_files[0]
        logger.info(f"Memproses audit Veridoc (single): file={file.filename}, zona={utm_zone}, datum={datum}")
        
        try:
            content = await file.read()
            
            if len(content) == 0:
                raise HTTPException(status_code=400, detail="File PDF kosong (0 bytes).")
            
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Ukuran file melebihi batas 50MB.")
            
            result_data = process_audit_document(
                content, 
                file.filename,
                utm_zone=utm_zone,
                datum=datum,
                output_dir=output_dir
            )

            try:
                from database import save_audit_result_to_db
                save_audit_result_to_db(file.filename, result_data)
            except Exception as e:
                logger.error(f"Gagal menyimpan ke database geospasial: {e}")

            safe_name = file.filename.replace(' ', '_').replace('"', '')
            result_data['filename'] = f"Laporan_Veridoc_{safe_name}"
            result_data['mode'] = 'single'
            
            return JSONResponse(content=result_data)
            
        except HTTPException:
            raise
        except ValueError as e:
            logger.warning(f"Parsing error: {e}")
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Terjadi kesalahan internal Veridoc: {str(e)}")
    
    # --- MULTI FILE MODE ---
    logger.info(f"Memproses audit Veridoc (multi): {len(pdf_files)} file PDF")
    results = []
    total_points_all = 0
    total_pass_all = 0
    total_fail_all = 0
    
    for file in pdf_files:
        content = await file.read()
        if len(content) == 0:
            continue
        
        try:
            res = process_audit_document(
                content, file.filename,
                utm_zone=utm_zone, datum=datum,
                output_dir=output_dir
            )
            safe_name = file.filename.replace(' ', '_').replace('"', '')
            res['filename'] = file.filename
            res['report_filename'] = f"Laporan_Veridoc_{safe_name}"
            res['original_filename'] = file.filename
            
            try:
                from database import save_audit_result_to_db
                save_audit_result_to_db(file.filename, res)
            except Exception as e:
                logger.error(f"Gagal menyimpan batch ke database geospasial: {e}")
            
            results.append(res)
            total_points_all += res.get('total_points', 0)
            total_pass_all += res.get('pass_count', 0)
            total_fail_all += res.get('fail_count', 0)
        except Exception as e:
            logger.warning(f"Gagal memproses file {file.filename}: {e}")
            results.append({
                "status": "error",
                "original_filename": file.filename,
                "error": str(e)
            })
    
    batch_pdf_b64, batch_pdf_path = generate_consolidated_batch_pdf_report(results, output_dir=output_dir)

    return JSONResponse(content={
        "status": "success",
        "mode": "multi",
        "total_files": len(results),
        "total_points_all": total_points_all,
        "total_pass_all": total_pass_all,
        "total_fail_all": total_fail_all,
        "pdf_base64": batch_pdf_b64,
        "saved_path": batch_pdf_path,
        "filename": "Laporan_Konsolidasi_Batch_Veridoc",
        "batch_results": results
    })

@app.post("/api/export/geojson")
async def export_geojson(payload: Dict[str, Any]):
    """Export audited points to GeoJSON FeatureCollection."""
    points = payload.get("points", [])
    features = []
    for p in points:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p.get("lon_dd", 0), p.get("lat_dd", 0)]
            },
            "properties": {
                "TK_Code": p.get("code"),
                "Page_PDF": p.get("page"),
                "Lat_DMS": p.get("lat_dms"),
                "Lon_DMS": p.get("lon_dms"),
                "Doc_X": p.get("doc_x"),
                "Doc_Y": p.get("doc_y"),
                "Calc_X": p.get("calc_x"),
                "Calc_Y": p.get("calc_y"),
                "dX_m": p.get("dx"),
                "dY_m": p.get("dy"),
                "Zone": p.get("zone")
            }
        })
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    return Response(
        content=json.dumps(geojson_data, indent=2),
        media_type="application/geo+json",
        headers={"Content-Disposition": "attachment; filename=Veridoc_Audited_Points.geojson"}
    )

@app.post("/api/export/kml")
async def export_kml(payload: Dict[str, Any]):
    """Export audited points to KML format for Google Earth."""
    points = payload.get("points", [])
    kml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
    kml_str += '<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n'
    kml_str += '  <name>Veridoc Audited Points</name>\n'
    for p in points:
        kml_str += '  <Placemark>\n'
        kml_str += f'    <name>{p.get("code")}</name>\n'
        kml_str += f'    <description>Halaman PDF: {p.get("page")}&#10;dX: {p.get("dx")}m&#10;dY: {p.get("dy")}m</description>\n'
        kml_str += f'    <Point><coordinates>{p.get("lon_dd")},{p.get("lat_dd")},0</coordinates></Point>\n'
        kml_str += '  </Placemark>\n'
    kml_str += '</Document>\n</kml>'
    return Response(
        content=kml_str,
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": "attachment; filename=Veridoc_Audited_Points.kml"}
    )

@app.post("/api/audit/batch")
async def audit_pdf_batch(
    files: List[UploadFile] = File(...),
    utm_zone: str = Form("Auto"),
    datum: str = Form("EPSG:4326"),
    output_dir: Optional[str] = Form(None)
):
    """Memproses audit se-folder PDF secara batch bersamaan."""
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Tidak ada file PDF yang diunggah.")
    
    logger.info(f"Memproses audit Batch Veridoc: {len(files)} file PDF")
    
    results = []
    total_points_all = 0
    total_pass_all = 0
    total_fail_all = 0
    
    for file in files:
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            continue
        
        content = await file.read()
        if len(content) == 0:
            continue
            
        try:
            res = process_audit_document(
                content,
                file.filename,
                utm_zone=utm_zone,
                datum=datum,
                output_dir=output_dir
            )
            safe_name = file.filename.replace(' ', '_').replace('"', '')
            res['filename'] = file.filename
            res['report_filename'] = f"Laporan_Veridoc_{safe_name}"
            res['original_filename'] = file.filename
            
            # Simpan hasil audit batch ke database geospasial
            try:
                from database import save_audit_result_to_db
                save_audit_result_to_db(file.filename, res)
            except Exception as e:
                logger.error(f"Gagal menyimpan batch ke database geospasial: {e}")
                
            results.append(res)

            
            total_points_all += res['total_points']
            total_pass_all += res['pass_count']
            total_fail_all += res['fail_count']
        except Exception as e:
            logger.warning(f"Gagal memproses file batch {file.filename}: {e}")
            results.append({
                "status": "error",
                "original_filename": file.filename,
                "error": str(e)
            })

    return JSONResponse(content={
        "status": "success",
        "total_files": len(results),
        "total_points_all": total_points_all,
        "total_pass_all": total_pass_all,
        "total_fail_all": total_fail_all,
        "batch_results": results
    })

@app.get("/api/regulations")
async def get_regulations():
    """Mengembalikan daftar acuan regulasi geospasial & Kemendagri terkini."""
    from audit_engine import LATEST_REGULATIONS
    return JSONResponse(content={"status": "success", "regulations": LATEST_REGULATIONS})

@app.get("/api/regulations/search")
async def search_regulations(q: str = ""):
    """Pencarian regulasi geospasial terkini secara langsung."""
    from audit_engine import LATEST_REGULATIONS
    q_lower = q.lower().strip()
    if not q_lower:
        results = LATEST_REGULATIONS
    else:
        results = [
            r for r in LATEST_REGULATIONS 
            if (q_lower in r['title'].lower() or q_lower in r['topic'].lower() or q_lower in r['summary'].lower() or q_lower in r['authority'].lower())
        ]
    return JSONResponse(content={"status": "success", "query": q, "results": results})

@app.get("/api/ai-info")
async def get_ai_info():
    """Mengembalikan informasi modul AI, alasan penggunaan, dan akurasi masing-masing AI engine."""
    from audit_engine import AI_MODELS_INFO
    return JSONResponse(content={"status": "success", "ai_models": AI_MODELS_INFO})

# ═════════════════════════════════════════════════════════════════════════
# API WILAYAH KEMENDAGRI LIVE (PROVINSI, KABUPATEN, KECAMATAN, DESA)
# ═════════════════════════════════════════════════════════════════════════

@app.get("/api/wilayah/provinces")
async def get_wilayah_provinces():
    """Mengambil daftar seluruh Provinsi di Indonesia secara live via API Kemendagri."""
    from audit_engine import WilayahDatabase
    db = WilayahDatabase()
    res = db.fetch_provinces_live()
    return JSONResponse(content={"status": "success", "total": len(res), "provinces": res})

@app.get("/api/wilayah/regencies/{prov_code}")
async def get_wilayah_regencies(prov_code: str):
    """Mengambil daftar Kabupaten/Kota di bawah Provinsi secara live via API Kemendagri."""
    from audit_engine import WilayahDatabase
    db = WilayahDatabase()
    res = db.fetch_regencies_live(prov_code)
    return JSONResponse(content={"status": "success", "prov_code": prov_code, "total": len(res), "regencies": res})

@app.get("/api/wilayah/districts/{kab_code}")
async def get_wilayah_districts(kab_code: str):
    """Mengambil daftar Kecamatan di bawah Kabupaten/Kota secara live via API Kemendagri."""
    from audit_engine import WilayahDatabase
    db = WilayahDatabase()
    res = db.fetch_districts_live(kab_code)
    return JSONResponse(content={"status": "success", "kab_code": kab_code, "total": len(res), "districts": res})

@app.get("/api/wilayah/villages/{kec_code}")
async def get_wilayah_villages(kec_code: str):
    """Mengambil daftar Desa/Kelurahan di bawah Kecamatan secara live via API Kemendagri."""
    from audit_engine import WilayahDatabase
    db = WilayahDatabase()
    res = db.fetch_villages_live(kec_code)
    return JSONResponse(content={"status": "success", "kec_code": kec_code, "total": len(res), "villages": res})

@app.post("/api/wilayah/validate")
async def validate_wilayah_code(code: str = Form(...)):
    """Memeriksa keberadaan kode dan kecocokan hirarki Kemendagri (Prov -> Kab -> Kec -> Desa) secara live."""
    from audit_engine import WilayahDatabase
    db = WilayahDatabase()
    val_res = db.validate_hierarchy(code)
    return JSONResponse(content={"status": "success", "result": val_res})





@app.post("/api/sample/generate")
async def generate_sample_pdf(scenario: str = "with_anomalies"):
    """Generates a synthetic SKVT sample PDF in memory for testing/training AI engine."""
    try:
        from sample_generator import generate_sample_skvt_pdf
        pdf_bytes = generate_sample_skvt_pdf(scenario=scenario)
        filename = f"Sample_SKVT_BIG_{scenario}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error generating sample PDF: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Gagal membuat sample PDF: {str(e)}")

@app.post("/api/sample/run-audit")
async def run_sample_audit(scenario: str = "with_anomalies", utm_zone: str = "Auto", datum: str = "EPSG:4326"):
    """Generates a synthetic SKVT sample PDF and audits it directly."""
    try:
        from sample_generator import generate_sample_skvt_pdf
        pdf_bytes = generate_sample_skvt_pdf(scenario=scenario)
        filename = f"Sample_SKVT_BIG_{scenario}.pdf"
        result_data = process_audit_document(
            pdf_bytes,
            filename,
            utm_zone=utm_zone,
            datum=datum
        )
        result_data['filename'] = f"Laporan_Veridoc_Sample_{scenario}"
        return JSONResponse(content=result_data)
    except Exception as e:
        logger.error(f"Error running sample audit: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Gagal menguji sample PDF: {str(e)}")

@app.get("/api/database/spatial")
async def get_spatial_db():
    """Mengambil data hasil audit spasial dari DuckDB."""
    try:
        import duckdb
        conn = duckdb.connect("veridoc.duckdb")
        conn.execute("LOAD spatial;")
        # Ambil 50 data terbaru
        res = conn.execute("""
            SELECT id, filename, audit_date, audit_score, status, 
                   ST_AsText(geometry) as geom_wkt 
            FROM audit_logs 
            ORDER BY audit_date DESC LIMIT 50
        """).fetchall()
        
        data = []
        for row in res:
            data.append({
                "id": row[0],
                "filename": row[1],
                "audit_date": str(row[2]),
                "audit_score": row[3],
                "status": row[4],
                "geometry_wkt": row[5]
            })
        return JSONResponse(content={"status": "success", "data": data})
    except Exception as e:
        logger.error(f"Error fetching spatial db: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": "Veridoc", "version": "3.5.0"}

frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

