"""
services/monitoring_service.py — Server Metrics Collection

Uses the `psutil` library to collect real-time system information:
    - CPU usage percentage
    - Memory (RAM) usage
    - Disk usage
    - System uptime
    - Network stats

Also queries SQLite to provide database-level stats.

Why psutil?
    - Works on Linux, macOS, and Windows
    - No system admin access required
    - Same library used by monitoring tools like Glances, htop, and netdata
"""

import logging
import platform
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MonitoringService:
    """Collects and returns server and application metrics."""

    def __init__(self):
        try:
            import psutil
            psutil.cpu_percent(interval=None)  # prime timer for non-blocking calls
        except Exception:
            pass

    # ── Server metrics (psutil) ───────────────────────────────────────
    def get_server_metrics(self) -> dict:
        """
        Return a dict of current server resource usage.

        Gracefully returns zero/None values if psutil is unavailable.
        """
        try:
            import psutil

            # CPU — interval=None returns non-blocking percentage since last call
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_count   = psutil.cpu_count(logical=True)

            # Memory
            mem         = psutil.virtual_memory()
            mem_percent = mem.percent
            mem_used_mb = round(mem.used / (1024 ** 2), 1)
            mem_total_mb = round(mem.total / (1024 ** 2), 1)
            mem_avail_mb = round(mem.available / (1024 ** 2), 1)

            # Disk — root partition
            disk         = psutil.disk_usage("/")
            disk_percent = disk.percent
            disk_used_gb = round(disk.used / (1024 ** 3), 2)
            disk_total_gb = round(disk.total / (1024 ** 3), 2)
            disk_free_gb = round(disk.free / (1024 ** 3), 2)

            # System uptime
            boot_time       = psutil.boot_time()
            uptime_seconds  = int(datetime.utcnow().timestamp() - boot_time)
            uptime_human    = self.seconds_to_human(uptime_seconds)

            # Network I/O counters (cumulative since boot)
            net = psutil.net_io_counters()

            # Process count
            process_count = len(psutil.pids())

            return {
                "cpu_percent":    cpu_percent,
                "cpu_count":      cpu_count,
                "memory_percent": mem_percent,
                "memory_used_mb": mem_used_mb,
                "memory_total_mb": mem_total_mb,
                "memory_avail_mb": mem_avail_mb,
                "disk_percent":   disk_percent,
                "disk_used_gb":   disk_used_gb,
                "disk_total_gb":  disk_total_gb,
                "disk_free_gb":   disk_free_gb,
                "uptime_seconds": uptime_seconds,
                "uptime_human":   uptime_human,
                "net_bytes_sent": net.bytes_sent,
                "net_bytes_recv": net.bytes_recv,
                "process_count":  process_count,
                "platform":       platform.system(),
                "python_version": platform.python_version(),
                "status":         "ok",
            }

        except ImportError:
            logger.warning("psutil not installed — returning placeholder metrics")
            return self._placeholder_metrics()

        except Exception as exc:
            logger.error(f"Error collecting server metrics: {exc}")
            return self._placeholder_metrics(error=str(exc))

    def _placeholder_metrics(self, error: str = "psutil not available") -> dict:
        """Return safe placeholder values when real metrics can't be collected."""
        return {
            "cpu_percent":    0,
            "cpu_count":      1,
            "memory_percent": 0,
            "memory_used_mb": 0,
            "memory_total_mb": 0,
            "memory_avail_mb": 0,
            "disk_percent":   0,
            "disk_used_gb":   0,
            "disk_total_gb":  0,
            "disk_free_gb":   0,
            "uptime_seconds": 0,
            "uptime_human":   "unknown",
            "net_bytes_sent": 0,
            "net_bytes_recv": 0,
            "process_count":  0,
            "platform":       platform.system(),
            "python_version": platform.python_version(),
            "status":         "error",
            "error":          error,
        }

    # ── Database statistics ───────────────────────────────────────────
    def get_database_stats(self) -> dict:
        """
        Query the database and return aggregate stats.
        Called by /api/metrics to populate the dashboard.
        """
        try:
            from database.models import db, User, FileRecord
            from sqlalchemy import func

            total_users = User.query.count()

            total_files = FileRecord.query.filter_by(is_deleted=False).count()

            storage_bytes = db.session.query(
                func.sum(FileRecord.file_size)
            ).filter_by(is_deleted=False).scalar() or 0

            s3_files = FileRecord.query.filter_by(
                storage_backend="s3", is_deleted=False
            ).count()

            local_files = FileRecord.query.filter_by(
                storage_backend="local", is_deleted=False
            ).count()

            # Recent uploads in last 24 hours
            from datetime import timezone
            yesterday = datetime.utcnow() - timedelta(hours=24)
            recent_uploads = FileRecord.query.filter(
                FileRecord.uploaded_at >= yesterday,
                FileRecord.is_deleted == False
            ).count()

            return {
                "status":         "connected",
                "total_users":    total_users,
                "total_files":    total_files,
                "storage_bytes":  storage_bytes,
                "storage_human":  self.bytes_to_human(storage_bytes),
                "s3_files":       s3_files,
                "local_files":    local_files,
                "recent_uploads": recent_uploads,
            }

        except Exception as exc:
            logger.error(f"Database stats error: {exc}")
            return {
                "status": "error",
                "error":  str(exc),
            }

    # ── Utility helpers ───────────────────────────────────────────────
    @staticmethod
    def seconds_to_human(seconds: int) -> str:
        """
        Convert seconds to a human-readable string.
        e.g. 90061 → "1 day, 1 hour, 1 minute"
        """
        if seconds <= 0:
            return "just started"

        days    = seconds // 86400
        hours   = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes and not days:   # hide minutes if we're showing days
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

        return ", ".join(parts) if parts else "less than a minute"

    @staticmethod
    def bytes_to_human(size_bytes: int) -> str:
        """Convert bytes to a human-readable string (e.g. '2.4 MB')."""
        if size_bytes == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
