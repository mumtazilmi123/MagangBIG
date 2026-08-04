import os
import sys
import traceback
from audit_engine import process_audit_document
from sample_generator import generate_sample_skvt_pdf

print("=== 1. TESTING SYNTHETIC SAMPLE PDF (SUMENEP ANOMALIES) ===")
try:
    pdf_bytes = generate_sample_skvt_pdf(scenario="sumenep_anomalies")
    res = process_audit_document(pdf_bytes, "Sample_Sumenep.pdf")
    print(f"Status: {res.get('status')}")
    print(f"Region: {res.get('region')}")
    print(f"Total Points: {res.get('total_points')}")
    print(f"CE95: {res.get('ce95')}m")
    print(f"Anomalies Count: {len(res.get('anomalies', []))}")
    print("\nRULES AUDIT SUMMARY:")
    for a in res.get('anomalies', []):
        status_icon = "❌" if a['status'] == "FAIL" else ("⚠️" if a['status'] == "WARNING" else "✅")
        print(f" [{a['id']}] {status_icon} {a['title']} - {a['status']} ({a['page_label']})")
        for d in a.get('details', []):
            print(f"     -> {d}")

except Exception as e:
    print(f"Error testing sample: {e}")
    traceback.print_exc()

print("\n=== 2. TESTING REAL PDF DOCUMENTS ===")
sumenep_pdf = r'c:\Users\Lenovo\OneDrive\Documents\KP_BIG\Dokumen\Draft SKVT_Verifikasi Batas Desa Kelurahan di Kabupaten Sumenep_Rev_4.pdf'
konawe_pdf = r'c:\Users\Lenovo\OneDrive\Documents\KP_BIG\Dokumen\Surat Keterangan Hasil Verifikasi Teknis Kabupaten Konawe Selatan.pdf'

for name, path in [("Sumenep", sumenep_pdf), ("Konawe", konawe_pdf)]:
    if os.path.exists(path):
        try:
            with open(path, 'rb') as f:
                content = f.read()
            res = process_audit_document(content, f'{name}.pdf')
            print(f"\n[OK] {name}: Region={res.get('region')}, Total Points={res.get('total_points')}, CE95={res.get('ce95')}m")
            print("  Flagged Rules:")
            for a in res.get('anomalies', []):
                if a['status'] != "PASS":
                    print(f"    - [{a['status']}] Rule {a['id']}: {a['title']} -> {a['message']}")
                    for d in a.get('details', []):
                        print(f"        -> Issue: {d.get('issue') if isinstance(d, dict) else d}")
                        if isinstance(d, dict) and d.get('context'):
                            print(f"        -> Konteks Asli: {d.get('context')}")
        except Exception as e:
            print(f"\n[FAIL] {name}: {e}")
            traceback.print_exc()
    else:
        print(f"\nFile {path} not found (skipping local test file).")
