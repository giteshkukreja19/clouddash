"""
Cloud File Management & Monitoring Dashboard
Flask Application Entry Point

This file creates and configures the Flask application.
"""

import os
import logging
from datetime import datetime
from flask import Flask, jsonify, request, redirect, url_for
from flask_login import LoginManager
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# Import database instance
from database.models import db, User

# Import route blueprints
from routes.auth import auth_bp
from routes.files import files_bp
from routes.monitoring import monitoring_bp

# ─────────────────────────────────────────────
# Application start time (used for uptime calc)
# ─────────────────────────────────────────────
APP_START_TIME = datetime.utcnow()


def create_app(config_name: str = None) -> Flask:
    """
    Application factory — creates and returns a configured Flask app.

    Using a factory function (instead of a global app object) makes the
    app easier to test and more flexible for different environments.
    """
    app = Flask(__name__)

    # ── Load configuration ────────────────────────────────────────────
    from config import config_by_name, Config

    env = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_by_name.get(env, Config))

    # ── Set up structured logging ─────────────────────────────────────
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
    )
    app.logger.setLevel(log_level)

    # ── Initialise database ───────────────────────────────────────────
    db.init_app(app)

    # ── Initialise Flask-Login ────────────────────────────────────────
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"          # redirect target
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id: str):
        """Tell Flask-Login how to reload a user from the session."""
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        """
        Custom unauthorized handler.
        Returns JSON 401 for API requests (/api/*) and redirects HTML requests to /login.
        """
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401
        return redirect(url_for("auth.login_page"))

    # ── Register blueprints (route groups) ───────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(monitoring_bp)

    # ── Create database tables if they don't exist ────────────────────
    with app.app_context():
        db.create_all()
        app.logger.info("Database tables verified/created.")

    # ── Store app start time on app object ────────────────────────────
    app.start_time = APP_START_TIME

    # ── Global JSON error handlers ────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "message": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden", "message": "Access denied"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found", "message": str(e)}), 404

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({
            "error": "File too large",
            "message": f"Maximum upload size is {app.config.get('MAX_CONTENT_LENGTH', 0) // (1024*1024)} MB"
        }), 413

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Internal server error: {e}")
        return jsonify({"error": "Internal server error", "message": "Something went wrong"}), 500

    app.logger.info(f"Cloud Dashboard app started in '{env}' mode.")
    return app


# ─────────────────────────────────────────────────────────────────────
# Run directly:  python app.py
# Production:    gunicorn -w 4 "app:create_app()"
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    flask_app = create_app()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    flask_app.run(host="0.0.0.0", port=port, debug=debug)
