"""
routes/auth.py — Authentication Routes

Handles user registration, login, logout, and session management.

Endpoints (HTML pages):
    GET  /               → Landing page (index.html)
    GET  /login          → Login form
    GET  /register       → Registration form
    GET  /dashboard      → Main app dashboard (protected)

Endpoints (REST API — called by JavaScript fetch()):
    POST /api/register   → Create a new account
    POST /api/login      → Authenticate and start a session
    POST /api/logout     → End the session
    GET  /api/me         → Return current user info
"""

import re
import logging
from datetime import datetime

from flask import (
    Blueprint, request, jsonify, render_template, current_app,
    redirect, url_for, session
)
from flask_login import (
    login_user, logout_user, login_required, current_user
)

from database.models import db, User

logger = logging.getLogger(__name__)

# Blueprint groups all auth routes under a common name.
# url_prefix is intentionally NOT set here so we can have routes at /
# and also at /api/...
auth_bp = Blueprint("auth", __name__)


# ─────────────────────────────────────────────────────────────────────
# HTML Page Routes — serve Jinja2 templates
# ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/")
def index():
    """Landing page — visible to everyone."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))
    return render_template("index.html")


@auth_bp.route("/login")
def login_page():
    """Render the login form. Redirect authenticated users to dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))
    return render_template("login.html")


@auth_bp.route("/register")
def register_page():
    """Render the registration form."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))
    return render_template("register.html")


@auth_bp.route("/dashboard")
@login_required   # Flask-Login redirects to /login if not authenticated
def dashboard():
    """Main application dashboard — requires login."""
    return render_template(
        "dashboard.html",
        user=current_user,
        s3_configured=bool(current_app.config.get("S3_BUCKET_NAME")),
    )


# ─────────────────────────────────────────────────────────────────────
# API Routes — return JSON responses
# ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/api/register", methods=["POST"])
def api_register():
    """
    POST /api/register

    Request body (JSON):
        {
            "username": "john_doe",
            "email":    "john@example.com",
            "password": "SecurePass123!"
        }

    Response (201 Created):
        { "message": "Account created successfully", "user": { ... } }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    # ── Extract and validate fields ────────────────────────────────
    username = (data.get("username") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    errors = _validate_registration(username, email, password)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    # ── Check for duplicate username / email ───────────────────────
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    # ── Create user ───────────────────────────────────────────────
    new_user = User(username=username, email=email)
    new_user.set_password(password)   # hashes password with Werkzeug

    try:
        db.session.add(new_user)
        db.session.commit()
        logger.info(f"New user registered: {username} ({email})")
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Registration DB error: {exc}")
        return jsonify({"error": "Database error. Please try again."}), 500

    # ── Auto-login after registration ─────────────────────────────
    login_user(new_user, remember=False)

    return jsonify({
        "message": "Account created successfully",
        "user": new_user.to_dict()
    }), 201


@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    """
    POST /api/login

    Request body (JSON):
        {
            "username": "john_doe",   # can also be email address
            "password": "SecurePass123!",
            "remember": true          # optional — extends session
        }

    Response (200 OK):
        { "message": "Login successful", "user": { ... } }
    """
    # Prevent re-login if already authenticated
    if current_user.is_authenticated:
        return jsonify({
            "message": "Already logged in",
            "user": current_user.to_dict()
        }), 200

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    identifier = (data.get("username") or "").strip()
    password   = data.get("password") or ""
    remember   = bool(data.get("remember", False))

    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required"}), 400

    # ── Find user by username OR email ────────────────────────────
    user = (
        User.query.filter_by(username=identifier).first()
        or User.query.filter_by(email=identifier).first()
    )

    if user is None or not user.check_password(password):
        # Generic message — don't reveal whether username or password was wrong
        logger.warning(f"Failed login attempt for identifier: {identifier!r}")
        return jsonify({"error": "Invalid username or password"}), 401

    if not user.is_active:
        return jsonify({"error": "This account has been deactivated"}), 403

    # ── Start session ─────────────────────────────────────────────
    login_user(user, remember=remember)

    # Record last login time
    user.last_login = datetime.utcnow()
    db.session.commit()

    logger.info(f"User logged in: {user.username}")
    return jsonify({
        "message": "Login successful",
        "user": user.to_dict()
    }), 200


@auth_bp.route("/api/logout", methods=["POST"])
@login_required
def api_logout():
    """
    POST /api/logout

    Clears the server-side session.

    Response (200 OK):
        { "message": "Logged out successfully" }
    """
    username = current_user.username
    logout_user()
    logger.info(f"User logged out: {username}")
    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.route("/api/me", methods=["GET"])
@login_required
def api_me():
    """
    GET /api/me

    Returns the currently authenticated user's profile.
    Used by the frontend to check session state on page load.

    Response (200 OK):
        { "user": { "id": 1, "username": "john_doe", ... } }
    """
    return jsonify({"user": current_user.to_dict()}), 200


# ─────────────────────────────────────────────────────────────────────
# Internal Helpers
# ─────────────────────────────────────────────────────────────────────

def _validate_registration(username: str, email: str, password: str) -> list:
    """
    Validate registration input fields.

    Returns a list of error strings — empty list means all fields are valid.
    """
    errors = []

    # Username validation
    if not username:
        errors.append("Username is required.")
    elif len(username) < 3:
        errors.append("Username must be at least 3 characters.")
    elif len(username) > 30:
        errors.append("Username must be 30 characters or fewer.")
    elif not re.match(r"^[a-zA-Z0-9_]+$", username):
        errors.append("Username may only contain letters, numbers, and underscores.")

    # Email validation
    if not email:
        errors.append("Email address is required.")
    elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("Please enter a valid email address.")

    # Password validation
    if not password:
        errors.append("Password is required.")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    elif len(password) > 128:
        errors.append("Password is too long (max 128 characters).")
    elif not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    elif not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one number.")

    return errors
