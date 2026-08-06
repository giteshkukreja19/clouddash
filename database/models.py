"""
database/models.py — SQLAlchemy ORM Models

Defines all database tables as Python classes.

Why SQLAlchemy?
  - Industry-standard Python ORM
  - Works with SQLite (local), PostgreSQL, MySQL (production)
  - To migrate from SQLite → PostgreSQL, change only DATABASE_URL in .env

Tables:
  - users        → stores registered accounts
  - files        → tracks every uploaded file and its metadata
  - upload_logs  → audit trail of every upload/delete action
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# db is the SQLAlchemy instance — shared across the whole app.
# It is initialised with the Flask app in app.py via db.init_app(app).
db = SQLAlchemy()


# ─────────────────────────────────────────────────────────────────────
# User Model
# ─────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    """
    Represents a registered user.

    UserMixin adds the properties Flask-Login needs:
        is_authenticated, is_active, is_anonymous, get_id()
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # User identity
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email    = db.Column(db.String(120), unique=True, nullable=False, index=True)

    # Passwords are NEVER stored as plain text.
    # We store only the bcrypt/scrypt hash produced by Werkzeug.
    password_hash = db.Column(db.String(256), nullable=False)

    # Account metadata
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationship: a user has many files
    # cascade="all, delete-orphan" → deleting a user also deletes their files
    files = db.relationship(
        "FileRecord",
        backref="owner",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # ── Password helpers ──────────────────────────────────────────────
    def set_password(self, plain_text: str) -> None:
        """Hash and store the password. Never store plain text."""
        self.password_hash = generate_password_hash(plain_text)

    def check_password(self, plain_text: str) -> bool:
        """Return True if the supplied password matches the stored hash."""
        return check_password_hash(self.password_hash, plain_text)

    # ── Serialisation ─────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Return a safe, JSON-serialisable representation (no password)."""
        return {
            "id":         self.id,
            "username":   self.username,
            "email":      self.email,
            "is_active":  self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


# ─────────────────────────────────────────────────────────────────────
# FileRecord Model
# ─────────────────────────────────────────────────────────────────────
class FileRecord(db.Model):
    """
    Tracks every uploaded file — both metadata and storage location.

    Storage locations:
        - S3:    s3_key is set, local_path may be empty after upload
        - Local: local_path is set, s3_key is None
    """

    __tablename__ = "files"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign key → users table
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # File identity
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename   = db.Column(db.String(255), nullable=False)  # UUID-prefixed safe name
    file_extension    = db.Column(db.String(20), nullable=True)

    # File properties
    file_size    = db.Column(db.BigInteger, default=0)   # bytes
    content_type = db.Column(db.String(100), nullable=True)

    # Storage location
    # s3_key is the full S3 object key, e.g. "uploads/user_1/abc123_myfile.pdf"
    s3_key     = db.Column(db.String(500), nullable=True)
    local_path = db.Column(db.String(500), nullable=True)

    # S3 public or pre-signed URL (stored for quick access, may expire)
    download_url = db.Column(db.String(1000), nullable=True)

    # Status
    storage_backend = db.Column(
        db.String(10),
        default="local",
        nullable=False
    )  # "s3" or "local"

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    deleted_at  = db.Column(db.DateTime, nullable=True)

    # ── Helpers ───────────────────────────────────────────────────────
    @property
    def file_size_human(self) -> str:
        """Return human-readable file size (e.g. '2.4 MB')."""
        size = self.file_size or 0
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def to_dict(self) -> dict:
        """Return JSON-serialisable dict for API responses."""
        return {
            "id":                self.id,
            "user_id":           self.user_id,
            "original_filename": self.original_filename,
            "stored_filename":   self.stored_filename,
            "file_extension":    self.file_extension,
            "file_size":         self.file_size,
            "file_size_human":   self.file_size_human,
            "content_type":      self.content_type,
            "s3_key":            self.s3_key,
            "storage_backend":   self.storage_backend,
            "download_url":      self.download_url,
            "is_deleted":        self.is_deleted,
            "uploaded_at":       self.uploaded_at.isoformat() if self.uploaded_at else None,
        }

    def __repr__(self) -> str:
        return f"<FileRecord id={self.id} name={self.original_filename!r} backend={self.storage_backend!r}>"


# ─────────────────────────────────────────────────────────────────────
# UploadLog Model  (audit trail)
# ─────────────────────────────────────────────────────────────────────
class UploadLog(db.Model):
    """
    Audit log — records every significant action taken on files.

    Useful for:
        - Debugging ("who deleted that file and when?")
        - CloudWatch / monitoring dashboards
        - Compliance in real-world systems
    """

    __tablename__ = "upload_logs"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    file_id    = db.Column(db.Integer, db.ForeignKey("files.id"), nullable=True)

    # Action type: "upload", "download", "delete", "list"
    action     = db.Column(db.String(50), nullable=False)

    # Extra context (JSON string)
    details    = db.Column(db.Text, nullable=True)

    # Client info for monitoring
    ip_address = db.Column(db.String(45), nullable=True)   # supports IPv6
    user_agent = db.Column(db.String(255), nullable=True)

    # Result
    success    = db.Column(db.Boolean, default=True, nullable=False)
    error_msg  = db.Column(db.Text, nullable=True)

    timestamp  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "user_id":    self.user_id,
            "file_id":    self.file_id,
            "action":     self.action,
            "details":    self.details,
            "ip_address": self.ip_address,
            "success":    self.success,
            "timestamp":  self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self) -> str:
        return f"<UploadLog id={self.id} action={self.action!r} success={self.success}>"
