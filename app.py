import os
import sys
from flask import Flask, send_from_directory, jsonify

# Add workspace directory to python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.database import init_db
from backend.config import UPLOADS_DIR
from backend.routes.auth_routes import auth_bp
from backend.routes.detect_routes import detect_bp
from backend.routes.pothole_routes import pothole_bp
from backend.routes.complaint_routes import complaint_bp
from backend.routes.repair_routes import repair_bp
from backend.routes.dashboard_routes import dashboard_bp
from backend.routes.report_routes import report_bp
from backend.routes.notification_routes import notification_bp
from backend.routes.user_routes import user_bp

def create_app():
    frontend_dir = os.path.join(BASE_DIR, 'frontend')
    app = Flask(__name__, static_folder=frontend_dir, static_url_path='')

    # Initialize Database
    init_db()

    # CORS Headers middleware
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

    # Serve static uploads
    @app.route('/uploads/<path:filename>')
    def serve_uploads(filename):
        return send_from_directory(UPLOADS_DIR, filename)

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(detect_bp, url_prefix='/api/detect')
    app.register_blueprint(pothole_bp, url_prefix='/api/potholes')
    app.register_blueprint(complaint_bp, url_prefix='/api/complaints')
    app.register_blueprint(repair_bp, url_prefix='/api/repairs')
    app.register_blueprint(dashboard_bp, url_prefix='/api')
    app.register_blueprint(report_bp, url_prefix='/api/reports')
    app.register_blueprint(notification_bp, url_prefix='/api/notifications')
    app.register_blueprint(user_bp, url_prefix='/api/users')

    # Catch-all route to serve frontend HTML pages
    @app.route('/')
    def serve_index():
        return send_from_directory(frontend_dir, 'index.html')

    @app.route('/<path:path>')
    def serve_frontend_pages(path):
        page_file = os.path.join(frontend_dir, path)
        if os.path.exists(page_file):
            return send_from_directory(frontend_dir, path)
        elif os.path.exists(f"{page_file}.html"):
            return send_from_directory(frontend_dir, f"{path}.html")
        return send_from_directory(frontend_dir, 'index.html')

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app

if __name__ == '__main__':
    app = create_app()
    print("\n" + "="*50)
    print(" 🚀 SMART ROAD & POTHOLE MONITORING SYSTEM")
    print(" 🌐 Server running at: http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
