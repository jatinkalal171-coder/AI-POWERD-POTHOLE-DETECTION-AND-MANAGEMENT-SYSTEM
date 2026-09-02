import os
import csv
import datetime
from backend.database import get_db
from backend.config import REPORTS_DIR
from backend.services.priority_service import calculate_road_health_score

def generate_csv_report_file():
    """
    Generate CSV report of all pothole records stored in SQLite database.
    Includes Complaint_ID (pothole_id), Confidence, Risk, Latitude, Longitude, Estimated_Distance_Meters, Status.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT pothole_id, detected_at, confidence, width, height, area, severity_score, priority_score, risk_level, latitude, longitude, estimated_distance, status
    FROM potholes
    ORDER BY priority_score DESC
    ''')
    rows = cursor.fetchall()
    conn.close()

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Pothole_Monitoring_Report_{stamp}.csv"
    csv_path = os.path.join(REPORTS_DIR, filename)

    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Complaint_ID", "Confidence", "Risk", 
            "Latitude", "Longitude", "Estimated_Distance_Meters", "Status"
        ])
        for r in rows:
            dist_val = f"{r['estimated_distance']:.1f}" if r['estimated_distance'] is not None else "N/A"

            writer.writerow([
                r['pothole_id'],
                f"{r['confidence']:.1f}%",
                r['risk_level'],
                r['latitude'] if r['latitude'] is not None else "",
                r['longitude'] if r['longitude'] is not None else "",
                dist_val,
                r['status']
            ])

    return csv_path

def generate_pdf_report_file():
    """
    Generate a styled PDF report using ReportLab with Estimated Distance metrics.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
    except ImportError:
        print("[ERROR] ReportLab package not installed.")
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT pothole_id, confidence, width, height, area, severity_score, risk_level, priority_score, road_name, status, detected_at, estimated_distance, annotated_image_path
    FROM potholes
    ORDER BY priority_score DESC
    ''')
    potholes = [dict(row) for row in cursor.fetchall()]
    conn.close()

    total_count = len(potholes)
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    valid_dists = []
    
    for p in potholes:
        risk_counts[p['risk_level']] = risk_counts.get(p['risk_level'], 0) + 1
        if p.get('estimated_distance') is not None:
            valid_dists.append(p['estimated_distance'])

    avg_dist_str = f"{sum(valid_dists)/len(valid_dists):.1f} m" if valid_dists else "N/A"

    health_info = calculate_road_health_score(potholes)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"Smart_Road_Inspection_Report_{stamp}.pdf"
    pdf_path = os.path.join(REPORTS_DIR, pdf_filename)

    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = []

    # Title Banner
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1a252f'),
        alignment=0
    )
    elements.append(Paragraph("AI-Powered Smart Road & Pothole Monitoring Report", title_style))
    elements.append(Paragraph(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Municipality Infrastructure Dept", styles['Italic']))
    elements.append(Spacer(1, 12))

    # Executive Summary Table
    summary_data = [
        ["Metric", "Value"],
        ["Total Potholes Monitored", str(total_count)],
        ["Average Estimated Distance", avg_dist_str],
        ["Road Health Score", f"{health_info['health_score']}/100 ({health_info['condition']})"],
        ["Critical Risk Count", str(risk_counts["CRITICAL"])],
        ["High Risk Count", str(risk_counts["HIGH"])],
        ["Medium Risk Count", str(risk_counts["MEDIUM"])],
        ["Low Risk Count", str(risk_counts["LOW"])]
    ]

    t_summary = Table(summary_data, colWidths=[240, 280])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa'))
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 15))

    # Recommendations Section
    elements.append(Paragraph("Automated Recommendations", styles['Heading2']))
    if health_info['health_score'] < 50:
        rec = "<b>URGENT INTERVENTION REQUIRED:</b> Immediate deployment of field repair units to Critical & High priority locations. Structural road rehabilitation recommended."
    elif health_info['health_score'] < 75:
        rec = "<b>SCHEDULED MAINTENANCE:</b> Priority repair recommended for High and Critical severity potholes within 5-7 business days."
    else:
        rec = "<b>ROUTINE MONITORING:</b> Road condition is satisfactory. Continue automated camera surveillance."

    elements.append(Paragraph(rec, styles['Normal']))
    elements.append(Spacer(1, 15))

    # Detailed Detections Table
    elements.append(Paragraph("Detailed Pothole Registry", styles['Heading2']))
    
    det_table_data = [["Complaint ID", "Location", "Conf", "Est Dist", "Severity", "Risk", "Status"]]
    for p in potholes[:15]:  # Limit top 15 in report
        dist_str = f"{p['estimated_distance']:.1f}m" if p.get('estimated_distance') is not None else "N/A"
        det_table_data.append([
            p['pothole_id'],
            p['road_name'][:20],
            f"{p['confidence']:.0f}%",
            dist_str,
            f"{p['severity_score']}/100",
            p['risk_level'],
            p['status']
        ])

    t_det = Table(det_table_data, colWidths=[80, 125, 45, 60, 60, 65, 70])
    t_det.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dcdde1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
    ]))
    elements.append(t_det)

    doc.build(elements)
    return pdf_path
