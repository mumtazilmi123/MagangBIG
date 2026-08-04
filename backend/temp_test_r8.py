import sys, os
sys.path.append('backend')
from audit_engine import audit_skvt_rules

sample_text = """
Daftar Koordinat Titik Batas Desa/Kelur
1 TK.74.05.21.2001-21.2009-000 4° 18' 17,18"
S 122° 2' 11
E
2 TK.74.05.21.2004-21.2007-001 4° 9' 5,40"
S 122° 13' 1
E
"""

anomalies = audit_skvt_rules(sample_text, [sample_text], [], None)
r8 = [a for a in anomalies if a['id'] == 8][0]

print("=== VERIFYING DETECTION OF SCREENSHOT ISSUES ===")
print("Rule 8 Status:", r8['status'])
print("Rule 8 Message:", r8['message'])
print("Total Issues Found:", len(r8['details']))
for idx, d in enumerate(r8['details']):
    print(f"Issue #{idx+1}: {d['issue']} | Context: {d['context']}")
