import os
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

def generate_pdf_report(payload: dict, output_path: str):
    """
    Generate professional PDF report using ReportLab.
    payload contains data from the frontend audit result.
    """
    doc = SimpleDocTemplate(
        output_path, 
        pagesize=A4,
        rightMargin=40, leftMargin=40, topMargin=50, bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#0ea5e9'), spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'HeadingStyle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#1e293b'), spaceAfter=8
    )
    normal_style = styles["Normal"]
    
    story = []
    
    # Header
    story.append(Paragraph(f"<b>GeoESG Audit Report: {payload.get('site_id', 'Unknown')}</b>", title_style))
    story.append(Paragraph(f"<b>Waktu Audit:</b> {datetime.datetime.now().strftime('%d %B %Y %H:%M:%S')}", normal_style))
    story.append(Paragraph(f"<b>Sistem:</b> GeoESG A.E.C.O Pipeline v2.2", normal_style))
    story.append(Spacer(1, 20))
    
    # Status
    status = payload.get('data_integrity_flag', '')
    is_pass = "PASS" in status
    status_text = "✅ AUDIT LULUS — Konsistensi Tinggi" if is_pass else "❌ AUDIT GAGAL — Akurasi Tidak Memenuhi Standar IPCC"
    status_color = colors.HexColor('#10b981') if is_pass else colors.HexColor('#ef4444')
    
    status_style = ParagraphStyle(
        'StatusStyle', parent=styles['Heading2'], fontSize=15, textColor=status_color, spaceAfter=20
    )
    story.append(Paragraph(f"<b>Status:</b> {status_text}", status_style))
    
    # Table 1: Metrik Satelit
    story.append(Paragraph("Metrik Satelit & Penginderaan Jauh", heading_style))
    data1 = [
        ['Parameter', 'Nilai'],
        ['NDVI Optik (Sentinel-2)', f"{payload.get('satellite_ndvi_90', 'N/A')}"],
        ['Tren NDVI (5 Tahun)', f"{payload.get('historical_trend_slope', 'N/A')}"],
        ['Status Ekologis', f"{payload.get('ecological_status', 'N/A')}"],
    ]
    t1 = Table(data1, colWidths=[200, 300])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t1)
    story.append(Spacer(1, 20))
    
    # Table 2: Estimasi Karbon
    story.append(Paragraph("Estimasi Karbon & Biomassa (SNI 7724:2011)", heading_style))
    data2 = [
        ['Parameter', 'Nilai'],
        ['Above-Ground Biomass (AGB)', f"{payload.get('estimated_biomass', 'N/A')} Mg/ha"],
        ['Stok Karbon', f"{payload.get('estimated_carbon', 'N/A')} Mg C/ha"],
    ]
    t2 = Table(data2, colWidths=[200, 300])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t2)
    story.append(Spacer(1, 20))
    
    # Table 3: Validasi Integritas (Standar IPCC)
    story.append(Paragraph("Validasi Integritas Data (Standar IPCC 2006)", heading_style))
    data3 = [
        ['Parameter', 'Nilai'],
        ['Field Biomass Ground Truth', f"{payload.get('ground_truth_biomass', 'N/A')} Mg/ha"],
        ['Relative Error (RE)', f"{payload.get('relative_error_pct', 'N/A')}%"],
        ['Bias', f"{payload.get('bias_mg_ha', 'N/A')} Mg/ha"],
        ['Akurasi', f"{payload.get('accuracy_pct', 'N/A')}%"],
        ['IPCC Tier', f"{payload.get('ipcc_tier', 'N/A')}"],
        ['Status Integritas', f"{status}"],
    ]
    t3 = Table(data3, colWidths=[200, 300])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t3)
    story.append(Spacer(1, 30))
    
    # Footer Note
    note_style = ParagraphStyle(
        'NoteStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#64748b'), leading=12
    )
    story.append(Paragraph(
        "<i>Catatan: Laporan ini dihasilkan secara otomatis menggunakan fusi data citra satelit (Optik dan SAR) "
        "yang tervalidasi dengan data lapangan. Integritas data diverifikasi menggunakan Relative Error (RE) "
        "terhadap ground truth sesuai standar IPCC 2006 Vol 4 Ch 2: "
        "Tier 3 (RE≤10%), Tier 2 (RE≤20%), Tier 1 (RE≤30%). Referensi: Chave et al. (2014).</i>",
        note_style
    ))
    
    doc.build(story)
    return output_path
