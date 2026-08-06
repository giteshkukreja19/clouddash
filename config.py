"""
config.py — Application Configuration

All settings are read from environment variables so that nothing
sensitive is ever stored in source code.

Usage in app.py:
    from config import config_by_name
    app.config.from_object(config_by_name["development"])
"""

import os
from datetime import timedelta


class Config:
    """
    Base configuration class.
    All other configs inherit from this.
    """

    # ── Flask core ────────────────────────────────────────────────────
    # SECRET_KEY is used to sign session cookies — must be long & random.
    # Generate one with:  python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-random-hex")

    # ── Session config ────────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True          # JS cannot read cookie
    SESSION_COOKIE_SAMESITE = "Lax"        # CSRF protection
    REMEMBER_COOKIE_DURATION = timedelta(days=7)

    # ── Database ──────────────────────────────────────────────────────
    # SQLite for local development.
    # To switch to PostgreSQL later, just change this one line:
    #   DATABASE_URL = "postgresql://user:pass@host/dbname"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///cloud_dashboard.db"   # stored in project root
    )
    SQLALCHEMY_DATABASE_URI: str = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False   # silence deprecation warning
    SQLALCHEMY_ECHO = False                  # set True to log every SQL query

    # ── File uploads ──────────────────────────────────────────────────
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024  # bytes

    # Local temp folder before file is pushed to S3
    UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "uploads")

    # Allowed file extensions (whitelist approach — safer than blacklist)
    ALLOWED_EXTENSIONS: set = {
        "png", "jpg", "jpeg", "gif", "webp",   # images
        "pdf",                                   # documents
        "txt", "md", "csv", "json", "xml",      # text / data
        "zip", "tar", "gz",                     # archives
        "py", "js", "html", "css",              # code files (good for demos)
        "docx", "xlsx", "pptx",                 # Office files
    }

    # ── AWS S3 ────────────────────────────────────────────────────────
    # NEVER hardcode these values here — always use environment variables.
    # On EC2, use an IAM Instance Role instead; then these can be empty.
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")

    # If S3 is not configured the app falls back to local /uploads storage.
    @property
    def S3_ENABLED(self) -> bool:
        return bool(self.S3_BUCKET_NAME)

    # ── Logging ───────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    """Local development — debug mode on, verbose logging."""
    DEBUG = True
    SQLALCHEMY_ECHO = False   # flip to True if you want to see SQL in terminal


class ProductionConfig(Config):
    """
    Production (EC2) — debug off, strict cookies.
    Remember to set SESSION_COOKIE_SECURE=True when using HTTPS.
    """
    DEBUG = False
    SESSION_COOKIE_SECURE = True    # only send cookie over HTTPS
    SESSION_COOKIE_HTTPONLY = True


class TestingConfig(Config):
    """Used in automated tests — in-memory SQLite, no side effects."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


# ── Mapping string → config class (used in app.py) ───────────────────
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
