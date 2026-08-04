import io
import os
import random
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from PIL import Image as PILImage, ImageDraw

def generate_sample_skvt_pdf(scenario="with_anomalies"):
    """
    Generates realistic SKVT BIG sample PDF documents for AI training & validation.
    
    Supported scenarios:
      - "clean": 100% compliant document (All Rules PASS).
      - "sumenep_anomalies": Replicates Sumenep SKVT with unreplaced ${ttd_pengirim}, blank date placeholders, spaced NIP, quote in village name.
      - "konawe_anomalies": Replicates Konawe Selatan SKVT with blank date placeholders & DMS notation mix.
      - "with_anomalies": Generic test document with font size/family mix, month typo ("Julid"), and invalid village code.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    styles = getSampleStyleSheet()

    title_font = "Helvetica-Bold"
    body_font = "Helvetica"
    body_font_size = 10
    
    alt_font = "Times-Roman" if scenario in ["with_anomalies", "sumenep_anomalies"] else "Helvetica"

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName=title_font,
        fontSize=12,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a")
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName=body_font,
        fontSize=body_font_size,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#334155")
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName=body_font,
        fontSize=8,
        leading=10,
        alignment=TA_CENTER
    )

    table_cell_alt_style = ParagraphStyle(
        'TableCellAlt',
        parent=styles['Normal'],
        fontName=alt_font,
        fontSize=8,
        leading=10,
        alignment=TA_CENTER
    )

    story = []

    # -------------------------------------------------------------
    # CONFIGURATION BASED ON SCENARIO
    # -------------------------------------------------------------
    if scenario == "sumenep_anomalies":
        reg_name = "Kabupaten Sumenep"
        prov_name = "Provinsi Jawa Timur"
        doc_no = "2.13/PBNR/IGD.04.05/7/2026"
        month_str = "Juli"
        ttd_placeholder = "${ttd_pengirim}"  # Unreplaced template variable!
        blank_date_sentence = "Pada hari           , tanggal        bulan          tahun 2026, telah selesai dilaksanakan Verifikasi Teknis..."
        nip_surveyor = "19931226 202421 2 006"  # Spaced NIP!
        village_31 = 'Banra"as'  # Quote symbol in village name!
        utm_sec_sep = "."
    elif scenario == "konawe_anomalies":
        reg_name = "Kabupaten Konawe Selatan"
        prov_name = "Provinsi Sulawesi Tenggara"
        doc_no = "17.5/PBNR/IGD.04.05/7/2026"
        month_str = "Juli"
        ttd_placeholder = ""
        blank_date_sentence = "Pada hari           , tanggal                       bulan          tahun 2026, telah selesai dilaksanakan Verifikasi Teknis..."
        nip_surveyor = "198209222006041002"
        village_31 = "Banracas"
        utm_sec_sep = ","
    elif scenario == "clean":
        reg_name = "Kabupaten Sumenep"
        prov_name = "Provinsi Jawa Timur"
        doc_no = "2.13/PBNR/IGD.04.05/7/2026"
        month_str = "Juli"
        ttd_placeholder = ""
        blank_date_sentence = "Pada hari Kamis, tanggal 2 bulan Juli tahun 2026, telah selesai dilaksanakan Verifikasi Teknis..."
        nip_surveyor = "199312262024212006"
        village_31 = "Banraas"
        utm_sec_sep = "."
    else:  # "with_anomalies" default
        reg_name = "di Konawe Selatan"  # Predicate missing
        prov_name = "Provinsi Sulawesi Tenggara"
        doc_no = "12.04/SKVT/BIG/VII/2026"
        month_str = "Julid"  # Typo month
        ttd_placeholder = "${ttd_pengirim}"
        blank_date_sentence = "Pada hari           , tanggal        bulan          tahun 2026, telah selesai dilaksanakan Verifikasi Teknis..."
        nip_surveyor = "19931226 202421 2 006"
        village_31 = "Desa Duduria"
        utm_sec_sep = ","

    # -------------------------------------------------------------
    # PAGE 1: SURAT KETERANGAN UTAMA
    # -------------------------------------------------------------
    story.append(Paragraph("<b>BADAN INFORMASI GEOSPASIAL (BIG)</b>", title_style))
    story.append(Paragraph("<b>SURAT KETERANGAN HASIL VERIFIKASI TEKNIS</b>", title_style))
    story.append(Paragraph(f"KEGIATAN PENEGASAN BATAS DESA/KELURAHAN {reg_name.upper()}, {prov_name.upper()}", title_style))
    story.append(Paragraph(f"NOMOR: {doc_no}", ParagraphStyle('Sub', parent=title_style, fontSize=10, leading=12)))
    story.append(Spacer(1, 15))

    p1_text = (
        f"Yang bertanda tangan di bawah ini, Nama: Khafid, NIP: 196703041987021002, "
        f"Jabatan: Direktur Pemetaan Batas Wilayah dan Nama Rupabumi, menerangkan bahwa "
        f"hasil kegiatan penegasan batas desa/kelurahan di {reg_name}, {prov_name} telah "
        f"sesuai spesifikasi verifikasi teknis penetapan dan penegasan batas desa/kelurahan pada tanggal 2 {month_str} 2026."
    )
    story.append(Paragraph(p1_text, body_style))
    story.append(Spacer(1, 15))

    signer_block = (
        "Direktur Pemetaan Batas Wilayah dan Nama Rupabumi,<br/><br/>"
    )
    if ttd_placeholder:
        signer_block += f"<font color='red'><b>{ttd_placeholder}</b></font><br/><br/>"
    else:
        signer_block += "<br/><br/>"
    signer_block += "<b>Khafid</b>"
    story.append(Paragraph(signer_block, body_style))
    story.append(PageBreak())

    # -------------------------------------------------------------
    # PAGE 2: LAMPIRAN I (HASIL VERIFIKASI & TANGGAL RUMPANG)
    # -------------------------------------------------------------
    story.append(Paragraph("<b>Lampiran I</b>", title_style))
    story.append(Paragraph("<b>HASIL VERIFIKASI TEKNIS KEGIATAN PENEGASAN BATAS DESA/KELURAHAN</b>", title_style))
    story.append(Paragraph(f"{reg_name.upper()}, {prov_name.upper()}", ParagraphStyle('Sub1', parent=title_style, fontSize=10, leading=12)))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"<b>{blank_date_sentence}</b>", body_style))
    story.append(Spacer(1, 12))

    kugi_data = [
        ["No", "Parameter Verifikasi Teknis", "Status", "Keterangan"],
        ["1", "Data Spasial Area Batas Format KUGI", "Lengkap", "Sesuai Spesifikasi BIG"],
        ["2", "Data Spasial Garis Batas Format KUGI", "Lengkap", "Sesuai Spesifikasi BIG"],
        ["3", "Data Spasial Titik Batas Format KUGI", "Lengkap", "Sesuai Spesifikasi BIG"],
        ["4", "Topologi & Atribut Data Spasial", "Sesuai", "Bebas Topologi Error"]
    ]

    t_kugi = Table(kugi_data, colWidths=[1*cm, 7*cm, 3*cm, 5*cm])
    t_kugi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ]))
    story.append(t_kugi)
    story.append(Spacer(1, 15))

    signer_surv = (
        "Mengetahui: Harry Ferdiansyah (NIP 197902252003121005)<br/>"
        f"Diperiksa oleh: Surveyor Pemetaan (NIP {nip_surveyor})"
    )
    story.append(Paragraph(signer_surv, body_style))
    story.append(PageBreak())

    # -------------------------------------------------------------
    # PAGE 3: LAMPIRAN II (DAFTAR DESA & PETA)
    # -------------------------------------------------------------
    story.append(Paragraph("<b>Lampiran II</b>", title_style))
    story.append(Paragraph("<b>Daftar Desa/Kelurahan yang Diverifikasi Teknis</b>", title_style))
    story.append(Spacer(1, 10))

    village_data = [
        ["No", "Kode Wilayah", "Desa / Kelurahan", "Kecamatan", "Kabupaten"],
        ["1", "35.29.16.2007", "Banuaju Timur", "Batang Batang", "Sumenep"],
        ["2", "35.29.16.2006", "Banuaju Barat", "Batang Batang", "Sumenep"],
        ["3", "35.29.18.2014", "Bancamara", "Dungkek", "Sumenep"],
        ["4", "35.29.18.2015", village_31, "Dungkek", "Sumenep"]
    ]

    t_v = Table(village_data, colWidths=[1*cm, 4*cm, 4.5*cm, 3.5*cm, 3.5*cm])
    t_v.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284c7")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ]))
    story.append(t_v)
    story.append(PageBreak())

    # -------------------------------------------------------------
    # PAGE 4: LAMPIRAN III (KOORDINAT TITIK KARTOMETRIK)
    # -------------------------------------------------------------
    story.append(Paragraph("<b>Lampiran III</b>", title_style))
    story.append(Paragraph("<b>Daftar Koordinat Titik Batas Desa/Kelurahan Hasil Pemeriksaan</b>", title_style))
    story.append(Spacer(1, 10))

    dir_sym1 = "E" if scenario in ["sumenep_anomalies", "with_anomalies"] else "BT"
    dir_sym2 = "S" if scenario in ["sumenep_anomalies", "with_anomalies"] else "LS"

    coord_rows = [
        ["No.", "Nomor Titik Batas", "Lintang", "Bujur", "UTM X", "UTM Y"],
        ["1", Paragraph("TK 35.29.19.2006-19.2010-004", table_cell_style), f"7° 2' 6{utm_sec_sep}335\" {dir_sym2}", f"113° 57' 1{utm_sec_sep}429\" {dir_sym1}", "825990,698", "9221343,033"],
        ["2", Paragraph("TK 35.29.19.2006-19.2010-005", table_cell_style), f"7° 2' 5{utm_sec_sep}746\" {dir_sym2}", f"113° 57' 0{utm_sec_sep}739\" {dir_sym1}", "825969,598", "9221361,279"],
        ["3", Paragraph("TK 35.29.19.2006-19.2010-003", table_cell_alt_style if scenario in ["sumenep_anomalies", "with_anomalies"] else table_cell_style), f"7° 1' 56{utm_sec_sep}001\" {dir_sym2}", f"113° 57' 9{utm_sec_sep}649\" {dir_sym1}", "826245,196", "9221659,174"],
    ]

    t_coord = Table(coord_rows, colWidths=[1*cm, 5*cm, 3*cm, 3*cm, 2*cm, 2.5*cm])
    t_coord.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f766e")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ]))
    story.append(t_coord)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
