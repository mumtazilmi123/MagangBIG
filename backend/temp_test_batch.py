import sys
sys.path.append('backend')
from audit_engine import process_audit_document, generate_consolidated_batch_pdf_report
from sample_generator import generate_sample_skvt_pdf

print("=== TESTING CONSOLIDATED BATCH REPORT PDF GENERATOR ===")
pdf1 = generate_sample_skvt_pdf('normal')
pdf2 = generate_sample_skvt_pdf('with_anomalies')

res1 = process_audit_document(pdf1, 'Konawe.pdf')
res2 = process_audit_document(pdf2, 'Sumenep.pdf')

b64, path = generate_consolidated_batch_pdf_report([res1, res2])
print("Consolidated PDF Generated Successfully!")
print("Saved Path:", path)
print("PDF Base64 Length:", len(b64))

print("\n=== TESTING RULE 8 ISSUE OUTPUT FORMAT (No Raw Text) ===")
r8 = [a for a in res2['anomalies_9'] if a['id'] == 8][0]
for idx, d in enumerate(r8['details'][:5]):
    print(f"Detail #{idx+1}: Issue = {d.get('issue')} | Context = {d.get('context')}")
