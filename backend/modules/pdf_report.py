import os
import html
import datetime
from io import BytesIO
import fitz
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

from .geodesy import sanitize_dms_string, clean_zone_display, format_tk_point_codes

BASE_PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VERIDOC_DIR = os.path.join(BASE_PROJECT_DIR, "Veridoc")
os.makedirs(VERIDOC_DIR, exist_ok=True)

def create_annotated_merged_pdf(orig_pdf_bytes: bytes, report_pdf_bytes: bytes) -> bytes:
    """
    Algoritma Pipeline PDF Veridoc (PyMuPDF / fitz):
    Menyisipkan PDF Laporan Audit Platypus ke bagian belakang dokumen PDF asli milik user.
    """
    try:
        doc_orig = fitz.open(stream=orig_pdf_bytes, filetype="pdf")
        doc_report = fitz.open(stream=report_pdf_bytes, filetype="pdf")
        doc_orig.insert_pdf(doc_report)
        final_pdf_bytes = doc_orig.write(garbage=1, deflate=True)

        doc_orig.close()
        doc_report.close()

        return final_pdf_bytes

    except Exception as e:
        print(f"[PyMuPDF Pipeline] Warning: Gagal menggabungkan PDF laporan: {e}")
        return report_pdf_bytes


def generate_consolidated_batch_pdf_report(batch_results, output_dir=None):
    """
    Menghasilkan 1 file PDF Laporan Konsolidasi Gabungan untuk seluruh dokumen batch,
    yang dipisahkan secara rapi per segmen wilayah/daerah.
    """
    target_dir = output_dir.strip() if (output_dir and output_dir.strip()) else VERIDOC_DIR
    os.makedirs(target_dir, exist_ok=True)

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle('BatchTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, alignment=TA_CENTER, spaceAfter=8, textColor=colors.HexColor('#0056A3'))
    style_subtitle = ParagraphStyle('BatchSubtitle', parent=styles['Heading2'], fontName='Helvetica', fontSize=10, alignment=TA_CENTER, spaceAfter=16, textColor=colors.dimgrey)
    style_sec_title = ParagraphStyle('SecTitle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, alignment=TA_LEFT, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor('#e5322d'))
    style_h2_bold = ParagraphStyle('BatchH2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10.5, textColor=colors.HexColor('#0056A3'), spaceBefore=10, spaceAfter=6)
    style_normal = ParagraphStyle('BatchNormal', parent=styles['Normal'], fontName='Helvetica', fontSize=8, alignment=TA_JUSTIFY, spaceAfter=4, leading=11)

    now = datetime.datetime.now().strftime("%d %B %Y, %H:%M WIB")
    elements = []

    elements.append(Paragraph("VERIDOC - LAPORAN KONSOLIDASI AUDIT BATCH GEOSPASIAL", style_title))
    elements.append(Paragraph(f"Pemeriksaan Multi-Dokumen SKVT BIG | Tanggal Audit: {now}", style_subtitle))

    valid_results = [r for r in batch_results if isinstance(r, dict) and r.get('status') != 'error']
    total_docs = len(valid_results)
    total_pts_all = sum(r.get('total_points', 0) for r in valid_results)
    total_anomalies_all = sum(sum(1 for a in r.get('anomalies_9', []) if a.get('status') != 'PASS') for r in valid_results)

    batch_summary_data = [
        [Paragraph("<b>Ringkasan Audit Batch:</b>", style_normal), Paragraph(f"<b>{total_docs} Dokumen PDF</b>", style_normal), Paragraph("<b>Total Titik Audited:</b>", style_normal), Paragraph(f"<b>{total_pts_all} Titik TK</b>", style_normal)],
        [Paragraph("<b>Status Konsolidasi:</b>", style_normal), Paragraph(f"<b>{total_anomalies_all} Total Catatan Evaluasi</b>", style_normal), Paragraph("<b>Metode Laporan:</b>", style_normal), Paragraph("<b>1 PDF Konsolidasi Tersegmentasi Per Daerah</b>", style_normal)]
    ]
    t_batch_sum = Table(batch_summary_data, colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
    t_batch_sum.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#0056A3')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f9ff'))
    ]))
    elements.append(t_batch_sum)
    elements.append(Spacer(1, 0.6*cm))

    for doc_idx, res in enumerate(valid_results, start=1):
        if doc_idx > 1:
            elements.append(PageBreak())

        region_name = res.get('region', f'Dokumen #{doc_idx}')
        orig_file = res.get('original_filename') or res.get('filename', f'File_{doc_idx}.pdf')
        skvt_no = res.get('components', {}).get('header_skvt', {}).get('skvt_no', 'N/A')
        signer_name = res.get('components', {}).get('header_skvt', {}).get('signer_name', '-')
        signer_nip = res.get('components', {}).get('header_skvt', {}).get('signer_nip', '-')

        elements.append(Paragraph(f"SEGMEN WILAYAH #{doc_idx}: {html.escape(str(region_name)).upper()}", style_sec_title))
        elements.append(Paragraph(f"File PDF: <b>{html.escape(str(orig_file))}</b> | SKVT No: <b>{html.escape(str(skvt_no))}</b> | TTD: <b>{html.escape(str(signer_name))} (NIP {html.escape(str(signer_nip))})</b>", style_normal))
        elements.append(Spacer(1, 0.3*cm))

        elements.append(Paragraph("<b>1. Matriks Hasil Pengecekan Parametrik:</b>", style_h2_bold))
        table_seg_data = [
            [Paragraph("<b>No</b>", style_normal), Paragraph("<b>Parameter Pengecekan</b>", style_normal), Paragraph("<b>Hal</b>", style_normal), Paragraph("<b>Status</b>", style_normal), Paragraph("<b>Detail Temuan & Rekomendasi</b>", style_normal)]
        ]

        anomalies = res.get('anomalies_9', [])
        for item in anomalies:
            st_text = f"<font color='green'><b>PASS</b></font>" if item['status'] == 'PASS' else (f"<font color='orange'><b>WARNING</b></font>" if item['status'] == 'WARNING' else f"<font color='red'><b>FAIL</b></font>")
            
            detail_combined = ""
            if item.get('details'):
                subset = item['details'][:4]
                sub_formatted = []
                for d in subset:
                    if isinstance(d, dict):
                        loc = f"[{html.escape(str(d.get('page_label', '')))}] " if d.get('page_label') else ""
                        iss = html.escape(str(d.get('issue', '')))
                        sugg = f" [Saran: {html.escape(str(d.get('suggestion', '')))}]" if d.get('suggestion') else ""
                        sub_formatted.append(f"{loc}{iss}{sugg}")
                    else:
                        sub_formatted.append(html.escape(str(d)))
                detail_combined += "• " + "<br/>• ".join(sub_formatted) + "<br/>"
            else:
                detail_combined += html.escape(str(item.get('message', ''))) + "<br/>"

            detail_combined += f"<b>Rekomendasi:</b> {html.escape(str(item.get('recommendation', '')))}"

            table_seg_data.append([
                str(item['id']),
                Paragraph(f"<b>{html.escape(str(item.get('title', '')))}</b>", style_normal),
                Paragraph(html.escape(str(item.get('page_label', ''))), style_normal),
                Paragraph(st_text, style_normal),
                Paragraph(detail_combined, style_normal)
            ])

        t_seg = Table(table_seg_data, colWidths=[0.9*cm, 4.2*cm, 1.8*cm, 1.8*cm, 9.3*cm])
        t_seg.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0056A3')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke)
        ]))
        elements.append(t_seg)
        elements.append(Spacer(1, 0.4*cm))

        pts = res.get('all_points', [])
        if pts:
            elements.append(Paragraph(f"<b>2. Tabel Koordinat Spasial ({len(pts)} Titik TK):</b>", style_h2_bold))
            table_pts_data = [[
                Paragraph("<b>No</b>", style_normal),
                Paragraph("<b>ID Titik TK</b>", style_normal),
                Paragraph("<b>Hal</b>", style_normal),
                Paragraph("<b>Lintang (DMS)</b>", style_normal),
                Paragraph("<b>Bujur (DMS)</b>", style_normal),
                Paragraph("<b>Zona</b>", style_normal),
                Paragraph("<b>dX (m)</b>", style_normal),
                Paragraph("<b>dY (m)</b>", style_normal)
            ]]
            cleaned_pts = format_tk_point_codes(pts[:650], region_name)
            for i_p, p_item in enumerate(cleaned_pts):
                c_disp = p_item.get('code_disp', f"TK-{i_p+1:03d}")
                lat_c = sanitize_dms_string(p_item.get('lat_dms', ''))
                lon_c = sanitize_dms_string(p_item.get('lon_dms', ''))
                zone_c = clean_zone_display(p_item.get('zone', '-'), p_item.get('lat_dd'))

                c_code_len = len(c_disp)
                c_tk_size = 6.0 if c_code_len > 32 else (6.5 if c_code_len > 24 else 7.5)

                table_pts_data.append([
                    str(i_p+1),
                    Paragraph(f"<font size={c_tk_size}><b>{html.escape(c_disp)}</b></font>", style_normal),
                    f"Hal {p_item.get('page', 1)}",
                    Paragraph(f"<font size=6.5>{html.escape(lat_c)}</font>", style_normal),
                    Paragraph(f"<font size=6.5>{html.escape(lon_c)}</font>", style_normal),
                    html.escape(zone_c),
                    f"{p_item.get('dx', 0.0):.4f}",
                    f"{p_item.get('dy', 0.0):.4f}"
                ])

            t_pts = Table(table_pts_data, colWidths=[0.7*cm, 4.2*cm, 1.1*cm, 3.4*cm, 3.4*cm, 1.0*cm, 1.3*cm, 1.3*cm])
            t_pts.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0056A3')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('FONTSIZE', (0,0), (-1,-1), 7.5),
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
            ]))
            elements.append(t_pts)

    pdf_b64 = ""
    batch_pdf_filename = f"Laporan_Konsolidasi_Batch_Veridoc_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    veridoc_pdf_path = os.path.join(target_dir, batch_pdf_filename)
    try:
        doc.build(elements)
        pdf_buffer.seek(0)
        pdf_bytes_out = pdf_buffer.read()
        with open(veridoc_pdf_path, 'wb') as f:
            f.write(pdf_bytes_out)
        import base64
        pdf_b64 = base64.b64encode(pdf_bytes_out).decode('utf-8')
    except Exception as pdf_err:
        print(f"Warning building consolidated batch PDF report: {pdf_err}")

    return pdf_b64, veridoc_pdf_path
