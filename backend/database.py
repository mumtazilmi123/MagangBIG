# pyrefly: ignore [missing-import]
import duckdb
import os
import json

DB_FILE = "veridoc.duckdb"

def init_db():
    """Inisialisasi DuckDB dan pasang ekstensi spatial."""
    conn = duckdb.connect(DB_FILE)
    try:
        # Load first to avoid unnecessary remote extension downloads/network delays
        try:
            conn.execute("LOAD spatial;")
        except Exception:
            try:
                conn.execute("INSTALL spatial;")
                conn.execute("LOAD spatial;")
            except Exception as inst_err:
                print(f"[DB Warning] Tidak dapat menginstal/memuat ekstensi spatial DuckDB: {inst_err}")

        # Create table for audit logs and spatial geometries
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY,
                filename VARCHAR,
                audit_date TIMESTAMP,
                audit_score DOUBLE,
                status VARCHAR,
                geometry GEOMETRY,
                audit_details JSON
            );
        """)
        
        # We can use a sequence for the ID
        conn.execute("CREATE SEQUENCE IF NOT EXISTS audit_seq;")
        
    except Exception as e:
        print(f"Error initializing geospatial database: {e}")
    finally:
        conn.close()

def save_audit_result_to_db(filename, audit_result):
    """
    Simpan hasil audit dan geometri batas koordinat (jika ada) ke DuckDB.
    """
    try:
        conn = duckdb.connect(DB_FILE)
        conn.execute("LOAD spatial;")
        
        score = audit_result.get('score', 0)
        status = audit_result.get('status', 'FAIL')
        
        # Coba ekstrak GeoJSON/WKT atau bounding box geometry
        geometry_wkt = None
        
        # Jika engine berhasil mengekstrak koordinat dan membuat bbox/polygon WKT
        # Untuk saat ini kita ambil bounding box kasar dari titik koordinat jika ada
        # Dalam audit engine, rule 10 / rule 11 biasanya punya info koordinat
        rules = audit_result.get('rules', [])
        all_coords = []
        for r in rules:
            if 'koordinat' in str(r.get('details', '')).lower() or 'geospasial' in str(r.get('details', '')).lower():
                # Ini contoh jika kita bisa parsing ulang, tapi kita asumsikan 
                # kita akan menyusun geom berdasarkan polygon batas
                pass
        
        details_json = json.dumps(audit_result)
        
        if geometry_wkt:
            conn.execute("""
                INSERT INTO audit_logs (id, filename, audit_date, audit_score, status, geometry, audit_details) 
                VALUES (nextval('audit_seq'), ?, current_timestamp, ?, ?, ST_GeomFromText(?), ?)
            """, [filename, score, status, geometry_wkt, details_json])
        else:
            conn.execute("""
                INSERT INTO audit_logs (id, filename, audit_date, audit_score, status, geometry, audit_details) 
                VALUES (nextval('audit_seq'), ?, current_timestamp, ?, ?, NULL, ?)
            """, [filename, score, status, details_json])
            
        print(f"[DB] Berhasil menyimpan audit log geospasial untuk {filename}")
        
    except Exception as e:
        print(f"[DB Error] Gagal menyimpan ke DB: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# Inisialisasi awal saat modul dimuat
init_db()
