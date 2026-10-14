"""
NEXUS E-Commerce — Main Application Server
Executes the Flask application, serves frontend assets, and exposes the DWM REST API.
"""

import os
import sys
import webbrowser

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from backend.database import init_db
from backend.etl_pipeline import execute_etl

try:
    from flask import Flask, send_from_directory
    from backend.routes import api

    app = Flask(__name__, static_folder=os.path.join(PROJECT_ROOT, 'frontend'))
    app.register_blueprint(api)

    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
        return response

    @app.route('/')
    def serve_index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/<path:path>')
    def serve_static(path):
        return send_from_directory(app.static_folder, path)

    def run_server():
        print("=" * 75)
        print("⚡ NEXUS E-Commerce — Operational Storefront & Executive Analytics Platform")
        print("=" * 75)
        print("Initializing Operational Database (SQLite) & Running Initial ETL Pipeline...")
        init_db()
        execute_etl()
        print("✓ Database & Analytical Star Schema Ready!")
        print("  - Database File: backend/nexus_ecommerce.db")
        print("  - Customer Login: demo@shop.in / demo123")
        print("  - Admin Login:    admin@shop.in / admin123")
        print("=" * 75)
        print("📡 Server running at: http://localhost:5000")
        print("=" * 75)

        try:
            webbrowser.open("http://localhost:5000")
        except Exception:
            pass

        app.run(host='0.0.0.0', port=5000, debug=False)

except ImportError:
    import http.server
    import socketserver

    class FallbackHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=os.path.join(PROJECT_ROOT, 'frontend'), **kwargs)

    def run_server():
        print("Notice: Flask not detected. Running on built-in HTTP server.")
        init_db()
        execute_etl()
        with socketserver.TCPServer(("", 5000), FallbackHandler) as httpd:
            print("Server running at: http://localhost:5000")
            httpd.serve_forever()

if __name__ == '__main__':
    run_server()
