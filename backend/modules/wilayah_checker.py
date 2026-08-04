import re
import html
from typing import Dict, List, Any, Optional, Tuple
from io import BytesIO
import pdfplumber

from .wilayah import WilayahDatabase

# Normalisasi text untuk perbandingan fleksibel (abaikan perbedaan spasi, kapital, gelar/tipe "Desa", "Kelurahan", "Kabupaten", "Kota")
def normalize_name(raw_name: Optional[str]) -> str:
    if not raw_name:
        return ""
    text = raw_name.strip().upper()
    # Hapus awalan umum jika ada
    text = re.sub(r'^(DESA|KELURAHAN|KEL|KECAMATAN|KEC|KABUPATEN|KAB|KOTA|PROVINSI|PROV)\b[\.\s]*', '', text)
    # Hapus tanda baca & spasi berlebih
    text = re.sub(r'[^A-Z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def calculate_name_similarity(name1: str, name2: str) -> bool:
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    if not norm1 or not norm2:
        return True  # Jika salah satu kosong/tidak diisi di dokumen, anggap kompatibel
    if norm1 == norm2:
        return True
    # Substring match (e.g., "BLANG TEUE" vs "DESA BLANG TEUE")
    if norm1 in norm2 or norm2 in norm1:
        return True
    return False

def identify_table_columns(header_row: List[Any]) -> Dict[str, int]:
    """
    Mengenali indeks kolom secara dinamis meskipun posisi kolom berubah.
    """
    col_map: Dict[str, int] = {}
    if not header_row:
        return col_map

    for idx, cell in enumerate(header_row):
        if not cell:
            continue
        c_text = str(cell).lower().strip()

        # Match Kode Wilayah
        if re.search(r'\b(kode\s*wilayah|kode\s*desa|kode\s*kel|kodifikasi|kode)\b', c_text) and 'code' not in col_map:
            col_map['code'] = idx
        # Match Desa/Kelurahan
        elif re.search(r'\b(desa/kelurahan|desa/kel|desa|kelurahan|gampong|nagari|pekon)\b', c_text) and 'desa' not in col_map:
            col_map['desa'] = idx
        # Match Kecamatan
        elif re.search(r'\b(kecamatan|kec)\b', c_text) and 'kecamatan' not in col_map:
            col_map['kecamatan'] = idx
        # Match Kabupaten/Kota
        elif re.search(r'\b(kabupaten/kota|kabupaten|kab/kota|kab|kota)\b', c_text) and 'kabupaten' not in col_map:
            col_map['kabupaten'] = idx
        # Match Provinsi
        elif re.search(r'\b(provinsi|prov)\b', c_text) and 'provinsi' not in col_map:
            col_map['provinsi'] = idx

    return col_map

def extract_wilayah_records_from_pdf(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Mendeteksi seluruh tabel pada dokumen dan mengestrak baris data wilayah,
    serta mendeteksi teks di luar tabel.
    """
    extracted_records: List[Dict[str, Any]] = []
    seen_combinations = set()

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as plumber_pdf:
            for page_idx, page in enumerate(plumber_pdf.pages):
                page_num = page_idx + 1

                # 1. Ekstraksi via Tabel
                tables = page.extract_tables()
                if tables:
                    for tbl_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            continue

                        # Cari baris header (biasanya baris 0 atau 1)
                        header_idx = -1
                        col_map = {}
                        for r_idx in range(min(3, len(table))):
                            possible_map = identify_table_columns(table[r_idx])
                            if 'code' in possible_map or ('desa' in possible_map and 'kecamatan' in possible_map):
                                header_idx = r_idx
                                col_map = possible_map
                                break

                        if header_idx != -1 and col_map:
                            for r_idx in range(header_idx + 1, len(table)):
                                row = table[r_idx]
                                if not row:
                                    continue

                                raw_code = str(row[col_map['code']]).strip() if 'code' in col_map and col_map['code'] < len(row) and row[col_map['code']] else ""
                                desa = str(row[col_map['desa']]).strip() if 'desa' in col_map and col_map['desa'] < len(row) and row[col_map['desa']] else ""
                                kec = str(row[col_map['kecamatan']]).strip() if 'kecamatan' in col_map and col_map['kecamatan'] < len(row) and row[col_map['kecamatan']] else ""
                                kab = str(row[col_map['kabupaten']]).strip() if 'kabupaten' in col_map and col_map['kabupaten'] < len(row) and row[col_map['kabupaten']] else ""
                                prov = str(row[col_map['provinsi']]).strip() if 'provinsi' in col_map and col_map['provinsi'] < len(row) and row[col_map['provinsi']] else ""

                                # Bersihkan newline dari ekstraksi tabel
                                raw_code = raw_code.replace('\n', ' ').strip()
                                desa = desa.replace('\n', ' ').strip()
                                kec = kec.replace('\n', ' ').strip()
                                kab = kab.replace('\n', ' ').strip()
                                prov = prov.replace('\n', ' ').strip()

                                # Cari match 10 digit bertitik atau angka
                                code_match = re.search(r'\b(\d{2}\.\d{2}\.\d{2}\.\d{4})\b', raw_code) or re.search(r'\b(\d{10})\b', raw_code)
                                if code_match:
                                    code_str = code_match.group(1)
                                    comb_key = f"{page_num}_{code_str}_{desa}_{kec}_{kab}"
                                    if comb_key not in seen_combinations:
                                        seen_combinations.add(comb_key)
                                        extracted_records.append({
                                            "source": f"Tabel (Hal {page_num})",
                                            "page": page_num,
                                            "code": code_str,
                                            "desa": desa,
                                            "kecamatan": kec,
                                            "kabupaten": kab,
                                            "provinsi": prov
                                        })

                # 2. Ekstraksi Teks Bebas (Key-Value atau Pasangan Kode)
                text = page.extract_text() or ""
                if text:
                    # Pola Key-Value: Kode Wilayah : 11.73.03.2017 ...
                    kv_code = re.search(r'Kode\s*Wilayah\s*[:=]\s*(\d{2}\.\d{2}\.\d{2}\.\d{4}|\d{10})', text, re.IGNORECASE)
                    kv_desa = re.search(r'(?:Desa|Kelurahan|Desa/Kelurahan)\s*[:=]\s*([^\n\r,]+)', text, re.IGNORECASE)
                    kv_kec = re.search(r'Kecamatan\s*[:=]\s*([^\n\r,]+)', text, re.IGNORECASE)
                    kv_kab = re.search(r'(?:Kabupaten|Kota|Kabupaten/Kota)\s*[:=]\s*([^\n\r,]+)', text, re.IGNORECASE)
                    kv_prov = re.search(r'Provinsi\s*[:=]\s*([^\n\r,]+)', text, re.IGNORECASE)

                    if kv_code:
                        code_str = kv_code.group(1).strip()
                        desa_str = kv_desa.group(1).strip() if kv_desa else ""
                        kec_str = kv_kec.group(1).strip() if kv_kec else ""
                        kab_str = kv_kab.group(1).strip() if kv_kab else ""
                        prov_str = kv_prov.group(1).strip() if kv_prov else ""

                        comb_key = f"{page_num}_{code_str}_{desa_str}_{kec_str}_{kab_str}"
                        if comb_key not in seen_combinations:
                            seen_combinations.add(comb_key)
                            extracted_records.append({
                                "source": f"Teks Dokumen (Hal {page_num})",
                                "page": page_num,
                                "code": code_str,
                                "desa": desa_str,
                                "kecamatan": kec_str,
                                "kabupaten": kab_str,
                                "provinsi": prov_str
                            })

                    # Pengecekan umum baris per baris untuk pola kode 10 digit jika belum pernah terekstrak
                    for line in text.split('\n'):
                        for m in re.finditer(r'\b(\d{2}\.\d{2}\.\d{2}\.\d{4})\b', line):
                            code_str = m.group(1)
                            if any(r['code'] == code_str and r['page'] == page_num for r in extracted_records):
                                continue

                            # Cari kata setelah kode
                            after = line[m.end():].strip()
                            parts = [p.strip() for p in re.split(r'\s{2,}|\t|;', after) if p.strip()]
                            d_val = parts[0] if len(parts) > 0 else ""
                            k_val = parts[1] if len(parts) > 1 else ""
                            b_val = parts[2] if len(parts) > 2 else ""

                            comb_key = f"{page_num}_{code_str}_{d_val}_{k_val}_{b_val}"
                            if comb_key not in seen_combinations:
                                seen_combinations.add(comb_key)
                                extracted_records.append({
                                    "source": f"Baris Teks (Hal {page_num})",
                                    "page": page_num,
                                    "code": code_str,
                                    "desa": d_val,
                                    "kecamatan": k_val,
                                    "kabupaten": b_val,
                                    "provinsi": ""
                                })
    except Exception as e:
        print(f"[WilayahChecker Error] Gagal membaca tabel/teks PDF: {e}")

    return extracted_records


def find_code_by_written_names(db_instance: WilayahDatabase, desa_name: str, kec_name: str, kab_name: str) -> Optional[str]:
    """
    Reverse lookup untuk menemukan Kode Wilayah 10-digit berdasarkan nama Desa, Kecamatan, dan Kabupaten.
    """
    if not (desa_name or kec_name or kab_name):
        return None

    provinces = db_instance.fetch_provinces_live()
    target_kab_code = None
    target_kec_code = None

    # Cari kabupaten/kota yang cocok
    if kab_name:
        for prov_code in provinces.keys():
            regs = db_instance.fetch_regencies_live(prov_code)
            for k_code, k_name in regs.items():
                if calculate_name_similarity(kab_name, k_name):
                    target_kab_code = k_code
                    break
            if target_kab_code:
                break

    # Cari kecamatan yang cocok
    if target_kab_code and kec_name:
        dists = db_instance.fetch_districts_live(target_kab_code)
        for c_code, c_name in dists.items():
            if calculate_name_similarity(kec_name, c_name):
                target_kec_code = c_code
                break

    # Cari desa yang cocok
    if target_kec_code and desa_name:
        vills = db_instance.fetch_villages_live(target_kec_code)
        for v_code, v_name in vills.items():
            if calculate_name_similarity(desa_name, v_name):
                return v_code

    return None


def audit_wilayah_consistency(pdf_bytes: bytes, db_instance: Optional[WilayahDatabase] = None) -> Dict[str, Any]:
    """
    Memeriksa kesesuaian Kode Wilayah pada seluruh dokumen terhadap database referensi Kemendagri
    menggunakan algoritma 3-tahap:
    - Tahap 1: Validasi Database (Per atribut)
    - Tahap 2: Majority Validation & Penentuan Atribut Salah (Kondisi 1, 2, 3, 4)
    - Tahap 3: Validasi Konteks Dokumen (Konsistensi Mayoritas Kabupaten/Kota Dokumen)
    """
    if db_instance is None:
        db_instance = WilayahDatabase()

    records = extract_wilayah_records_from_pdf(pdf_bytes)

    results: List[Dict[str, Any]] = []
    overall_pass = True
    total_checks = len(records)
    failed_checks = 0

    # Lacak pemetaan kode -> nama desa di dokumen untuk deteksi kode ganda / tertukar
    code_to_written_desa: Dict[str, List[Dict[str, Any]]] = {}

    for rec in records:
        code_str = rec["code"]
        doc_desa = rec["desa"]
        doc_kec = rec["kecamatan"]
        doc_kab = rec["kabupaten"]
        doc_prov = rec["provinsi"]

        code_to_written_desa.setdefault(code_str, []).append(rec)

        val_result = db_instance.validate_hierarchy(code_str)
        is_code_valid = val_result.get("hierarchy_valid", False)

        details_h = val_result.get("hierarchy_details", {})
        db_desa = details_h.get("desa", {}).get("name") if details_h.get("desa") else val_result.get("official_name")
        db_kec = details_h.get("kecamatan", {}).get("name")
        db_kab = details_h.get("kabupaten", {}).get("name")
        db_prov = details_h.get("provinsi", {}).get("name")

        # Tahap 1: Validasi Database (Per Atribut)
        code_match = is_code_valid
        desa_match = True if not doc_desa or not db_desa else calculate_name_similarity(doc_desa, db_desa)
        kec_match = True if not doc_kec or not db_kec else calculate_name_similarity(doc_kec, db_kec)
        kab_match = True if not doc_kab or not db_kab else calculate_name_similarity(doc_kab, db_kab)
        prov_match = True if not doc_prov or not db_prov else calculate_name_similarity(doc_prov, db_prov)

        mismatched_attrs = []
        if not code_match:
            mismatched_attrs.append("Kode Wilayah")
        if doc_desa and db_desa and not desa_match:
            mismatched_attrs.append("Nama Desa/Kelurahan")
        if doc_kec and db_kec and not kec_match:
            mismatched_attrs.append("Nama Kecamatan")
        if doc_kab and db_kab and not kab_match:
            mismatched_attrs.append("Nama Kabupaten/Kota")
        if doc_prov and db_prov and not prov_match:
            mismatched_attrs.append("Nama Provinsi")

        num_mismatches = len(mismatched_attrs)
        is_item_pass = (num_mismatches == 0)

        # Tahap 2: Penentuan Atribut yang Salah & Recommendations (Majority Validation)
        if num_mismatches == 0:
            status_text = "✓ Valid"
            mismatch_label = None
            rec_text = "Kode Wilayah dan seluruh nama wilayah sudah sesuai dengan database referensi."
        elif num_mismatches == 1:
            wrong_attr = mismatched_attrs[0]
            status_text = "✗ Tidak Sesuai"
            mismatch_label = f"Kesalahan pada {wrong_attr}"

            if wrong_attr == "Kode Wilayah":
                expected_code = find_code_by_written_names(db_instance, doc_desa, doc_kec, doc_kab)
                if expected_code:
                    rec_text = f"Kemungkinan terjadi kesalahan pada Kode Wilayah. Kode yang seharusnya: {expected_code}"
                else:
                    err_detail = val_result.get("error_message") or ""
                    rec_text = f"Kemungkinan terjadi kesalahan pada Kode Wilayah '{code_str}'. {err_detail}"

            elif wrong_attr == "Nama Desa/Kelurahan":
                rec_text = f"Kemungkinan terjadi kesalahan pada Nama Desa/Kelurahan. Nama yang seharusnya: {db_desa}"

            elif wrong_attr == "Nama Kecamatan":
                rec_text = f"Kemungkinan terjadi kesalahan pada Nama Kecamatan. Nama yang seharusnya: {db_kec}"

            elif wrong_attr == "Nama Kabupaten/Kota":
                rec_text = f"Kemungkinan terjadi kesalahan pada Nama Kabupaten/Kota. Nama yang seharusnya: {db_kab}"

            elif wrong_attr == "Nama Provinsi":
                rec_text = f"Kemungkinan terjadi kesalahan pada Nama Provinsi. Nama yang seharusnya: {db_prov}"

        elif num_mismatches == 2:
            status_text = "✗ Tidak Sesuai"
            mismatch_label = f"Ketidaksesuaian pada {mismatched_attrs[0]} dan {mismatched_attrs[1]}"
            rec_text = f"Periksa {mismatched_attrs[0]} dan {mismatched_attrs[1]} (berdasarkan acuan atribut lain yang valid pada database)."

        else:
            # Lebih dari 2 atribut tidak sesuai -> Kondisi 4
            status_text = "Perlu Verifikasi Manual"
            mismatch_label = "Perlu Verifikasi Manual"
            rec_text = f"Perlu Verifikasi Manual. Informasi tidak cukup kuat untuk memberikan rekomendasi otomatis ({', '.join(mismatched_attrs)} tidak sesuai)."

        # String ringkasan tertulis & DB
        written_parts = []
        if doc_desa: written_parts.append(f"Desa: {doc_desa}")
        if doc_kec: written_parts.append(f"Kec: {doc_kec}")
        if doc_kab: written_parts.append(f"Kab: {doc_kab}")
        if doc_prov: written_parts.append(f"Prov: {doc_prov}")
        written_str = ", ".join(written_parts) if written_parts else "Tidak disebutkan"

        db_parts = []
        if db_desa: db_parts.append(f"Desa: {db_desa}")
        if db_kec: db_parts.append(f"Kec: {db_kec}")
        if db_kab: db_parts.append(f"Kab: {db_kab}")
        if db_prov: db_parts.append(f"Prov: {db_prov}")
        expected_str = ", ".join(db_parts) if db_parts else "Tidak ditemukan"

        if not is_item_pass:
            overall_pass = False
            failed_checks += 1

        results.append({
            "source": rec["source"],
            "page": rec["page"],
            "code_in_doc": code_str,
            "written_in_doc": written_str,
            "written_details": {
                "desa": doc_desa,
                "kecamatan": doc_kec,
                "kabupaten": doc_kab,
                "provinsi": doc_prov
            },
            "expected_from_db": expected_str,
            "expected_details": {
                "desa": db_desa,
                "kecamatan": db_kec,
                "kabupaten": db_kab,
                "provinsi": db_prov
            },
            "is_valid": is_item_pass,
            "status_label": status_text,
            "mismatch_type": mismatch_label,
            "recommendation": rec_text,
            "context_warning": None
        })

    # Pengecekan Pertukaran Kode Wilayah & Kode Wilayah Ganda
    for code_key, occurrences in code_to_written_desa.items():
        distinct_desas = set(normalize_name(item["desa"]) for item in occurrences if item["desa"])
        if len(distinct_desas) > 1:
            overall_pass = False
            for r_item in results:
                if r_item["code_in_doc"] == code_key:
                    r_item["is_valid"] = False
                    desas_list_str = " dan ".join(list(set(item['desa'] for item in occurrences if item['desa'])))
                    dup_msg = f"Perhatian: Kode Wilayah '{code_key}' digunakan untuk lebih dari 1 desa berbeda ({desas_list_str}). Pastikan tidak ada kode yang tertukar."
                    if r_item["mismatch_type"]:
                        r_item["mismatch_type"] += ", Penggunaan Kode Wilayah Ganda"
                    else:
                        r_item["mismatch_type"] = "Penggunaan Kode Wilayah Ganda"
                    r_item["recommendation"] += f" {dup_msg}"

    # Tahap 3: Validasi Konteks Dokumen (Document-wide Majority Consistency)
    if records:
        kab_normalized_list = [normalize_name(r["kabupaten"]) for r in records if r["kabupaten"]]
        kab_raw_map = {normalize_name(r["kabupaten"]): r["kabupaten"] for r in records if r["kabupaten"]}
        if kab_normalized_list:
            from collections import Counter
            kab_counts = Counter(kab_normalized_list)
            most_common_kab_norm, top_count = kab_counts.most_common(1)[0]
            # Mayoritas jika kemunculan > 50% dari total baris berkabupaten
            if top_count > len(kab_normalized_list) / 2 and top_count > 1:
                dominant_kab_name = kab_raw_map.get(most_common_kab_norm, most_common_kab_norm)
                for r_item in results:
                    doc_k = r_item["written_details"]["kabupaten"]
                    if doc_k and normalize_name(doc_k) != most_common_kab_norm:
                        warning_msg = f"Warning: Kabupaten/Kota pada baris ini ('{doc_k}') berbeda dengan mayoritas isi dokumen ('{dominant_kab_name}'). Periksa kembali kemungkinan salah penulisan."
                        r_item["context_warning"] = warning_msg

    status_code = "PASS" if overall_pass else "FAIL"
    status_label = "✓ Kode Wilayah Sesuai" if overall_pass else "✗ Kode Wilayah Tidak Sesuai"

    return {
        "status": status_code,
        "status_label": status_label,
        "total_records_checked": total_checks,
        "failed_records": failed_checks,
        "items": results
    }

