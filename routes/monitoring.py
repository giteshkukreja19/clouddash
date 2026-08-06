"""
routes/monitoring.py — Health & Metrics Routes

Endpoints:
    GET /api/health    → Quick health check (is the app alive?)
    GET /api/metrics   → CPU, memory, disk, uptime, S3 status

These endpoints are called by:
    - The frontend dashboard to render monitoring cards
    - AWS CloudWatch agent or external uptime monitors
    - Load balancer health checks (on EC2)
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, current_app
from flask_login import login_required

from services.monitoring_service import MonitoringService

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint("monitoring", __name__)

_monitor = MonitoringService()   # singleton — creates once, reused per request


# ─────────────────────────────────────────────────────────────────────
# GET /api/health
# ─────────────────────────────────────────────────────────────────────
@monitoring_bp.route("/api/health", methods=["GET"])
def health_check():
    """
    Quick health endpoint — no authentication required.

    Used by:
        - AWS Elastic Load Balancer (ELB) target group health checks
        - Uptime monitoring services (UptimeRobot, Pingdom, etc.)
        - CI/CD pipelines to verify deployment succeeded

    Response (200):
        {
            "status": "healthy",
            "timestamp": "2024-01-15T10:30:00Z",
            "version": "1.0.0"
        }
    """
    try:
        # Verify database is reachable
        from database.models import db
        db.session.execute(db.text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error(f"Health check: DB not reachable — {exc}")
        db_status = "error"

    status = "healthy" if db_status == "connected" else "degraded"
    http_code = 200 if status == "healthy" else 503

    return jsonify({
        "status":    status,
        "database":  db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version":   "1.0.0",
    }), http_code


# ─────────────────────────────────────────────────────────────────────
# GET /api/metrics
# ─────────────────────────────────────────────────────────────────────
@monitoring_bp.route("/api/metrics", methods=["GET"])
@login_required
def get_metrics():
    """
    Full system metrics — requires authentication.

    Response (200):
        {
            "server": {
                "cpu_percent": 12.5,
                "memory_percent": 45.2,
                "memory_used_mb": 3200,
                "memory_total_mb": 8192,
                "disk_percent": 30.1,
                "disk_used_gb": 15.2,
                "disk_total_gb": 50.0,
                "uptime_seconds": 86400,
                "uptime_human": "1 day, 0:00:00"
            },
            "application": {
                "uptime_seconds": 3600,
                "uptime_human": "1 hour",
                "request_count": 150
            },
            "aws": {
                "s3_configured": true,
                "s3_bucket": "my-bucket",
                "region": "us-east-1"
            },
            "database": {
                "status": "connected",
                "total_users": 5,
                "total_files": 42,
                "total_storage_bytes": 10485760
            }
        }
    """
    metrics = {}

    # ── Server metrics (psutil) ───────────────────────────────────────
    metrics["server"] = _monitor.get_server_metrics()

    # ── Application uptime ────────────────────────────────────────────
    app_start = getattr(current_app, "start_time", datetime.utcnow())
    app_uptime_seconds = int((datetime.utcnow() - app_start).total_seconds())
    metrics["application"] = {
        "uptime_seconds": app_uptime_seconds,
        "uptime_human":   _monitor.seconds_to_human(app_uptime_seconds),
        "environment":    current_app.config.get("ENV", "development"),
    }

    # ── AWS / S3 status ───────────────────────────────────────────────
    s3_bucket = current_app.config.get("S3_BUCKET_NAME", "")
    aws_region = current_app.config.get("AWS_REGION", "us-east-1")
    metrics["aws"] = {
        "s3_configured": bool(s3_bucket),
        "s3_bucket":     s3_bucket or "Not configured",
        "region":        aws_region,
    }

    # Test S3 connectivity if configured
    if s3_bucket:
        try:
            from services.s3_service import S3Service
            s3 = S3Service()
            connection = s3.test_connection()
            metrics["aws"]["s3_status"] = (
                "connected" if connection["connected"] else "error"
            )
            if connection["error"]:
                metrics["aws"]["s3_error"] = connection["error"]
        except Exception as exc:
            metrics["aws"]["s3_status"] = "error"
            metrics["aws"]["s3_error"]  = str(exc)
    else:
        metrics["aws"]["s3_status"] = "not_configured"

    # ── Database stats ────────────────────────────────────────────────
    metrics["database"] = _monitor.get_database_stats()

    return jsonify(metrics), 200
