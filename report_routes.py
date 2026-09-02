import os
from flask import Blueprint, jsonify, send_file
from backend.services.report_service import generate_csv_report_file, generate_pdf_report_file

report_bp = Blueprint('reports', __name__)

@report_bp.route('/csv', methods=['GET'])
def download_csv_report():
    csv_path = generate_csv_report_file()
    if not os.path.exists(csv_path):
        return jsonify({"error": "Failed to generate CSV report"}), 500
    return send_file(csv_path, as_attachment=True, download_name=os.path.basename(csv_path))

@report_bp.route('/pdf', methods=['GET'])
def download_pdf_report():
    pdf_path = generate_pdf_report_file()
    if not pdf_path or not os.path.exists(pdf_path):
        return jsonify({"error": "Failed to generate PDF report. Ensure ReportLab is installed."}), 500
    return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
