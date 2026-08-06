"""
services/s3_service.py — AWS S3 Integration

Wraps all boto3 S3 operations so the rest of the app
never imports boto3 directly. If S3 is not configured,
methods return safe fallback values.

Why a wrapper class?
    - Centralises all S3 logic in one place
    - Easy to mock in tests
    - If you ever switch to Google Cloud Storage or Azure Blob,
      you only change this one file

AWS Credentials Resolution Order (boto3 does this automatically):
    1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    2. ~/.aws/credentials file (set up via `aws configure`)
    3. IAM Instance Role (when running on EC2) ← best for production
"""

import io
import logging
import os

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)


class S3Service:
    """Wrapper around boto3 S3 client."""

    def __init__(self):
        self._client = None
        config = current_app.config if has_app_context() else os.environ
        self._bucket = config.get("S3_BUCKET_NAME", "")
        self._region = config.get("AWS_REGION", "us-east-1")
        self._configured = bool(self._bucket)

    def _get_client(self):
        """
        Lazily create the boto3 S3 client.

        boto3 automatically reads credentials from:
            - Environment variables (local dev)
            - IAM Instance Role (EC2 production)
        Never pass credentials as arguments here.
        """
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("s3", region_name=self._region)
            except ImportError:
                logger.error("boto3 is not installed. Run: pip install boto3")
                raise
        return self._client

    def is_configured(self) -> bool:
        """Return True if S3_BUCKET_NAME is set."""
        return self._configured

    # ── Upload ────────────────────────────────────────────────────────
    def upload_fileobj(
        self,
        fileobj: bytes,
        s3_key: str,
        content_type: str = "application/octet-stream",
    ) -> tuple:
        """
        Upload bytes to S3.

        Args:
            fileobj:      File content as bytes
            s3_key:       S3 object key (path), e.g. "uploads/user_1/abc.pdf"
            content_type: MIME type of the file

        Returns:
            (success: bool, url: str, error: str)
        """
        if not self._configured:
            return False, "", "S3 is not configured"

        try:
            client = self._get_client()
            client.put_object(
                Bucket      = self._bucket,
                Key         = s3_key,
                Body        = fileobj,
                ContentType = content_type,
            )
            # Build the S3 URL (public access must be enabled on the bucket)
            url = f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{s3_key}"
            logger.info(f"Uploaded to S3: {s3_key}")
            return True, url, ""

        except Exception as exc:
            logger.error(f"S3 upload error for key={s3_key!r}: {exc}")
            return False, "", str(exc)

    # ── List objects ──────────────────────────────────────────────────
    def list_objects(self, prefix: str = "uploads/") -> list:
        """
        List objects in the bucket with a given prefix.

        Returns a list of dicts: [ { "key": ..., "size": ..., "last_modified": ... }, ... ]
        """
        if not self._configured:
            return []

        try:
            client   = self._get_client()
            response = client.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
            contents = response.get("Contents", [])
            return [
                {
                    "key":           obj["Key"],
                    "size":          obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
                for obj in contents
            ]
        except Exception as exc:
            logger.error(f"S3 list_objects error: {exc}")
            return []

    # ── Pre-signed download URL ───────────────────────────────────────
    def generate_presigned_url(self, s3_key: str, expiry_seconds: int = 3600) -> str:
        """
        Generate a temporary pre-signed URL for a private S3 object.

        The URL allows anyone with the link to download the file for
        `expiry_seconds` seconds (default: 1 hour).

        Args:
            s3_key:         S3 object key
            expiry_seconds: How long the URL is valid

        Returns:
            Pre-signed URL string, or empty string on error
        """
        if not self._configured:
            return ""

        try:
            client = self._get_client()
            url = client.generate_presigned_url(
                "get_object",
                Params     = {"Bucket": self._bucket, "Key": s3_key},
                ExpiresIn  = expiry_seconds,
            )
            return url
        except Exception as exc:
            logger.error(f"S3 presigned URL error for {s3_key!r}: {exc}")
            return ""

    # ── Delete ────────────────────────────────────────────────────────
    def delete_object(self, s3_key: str) -> bool:
        """
        Delete an object from S3.

        Returns True on success, False on failure.
        """
        if not self._configured:
            return False

        try:
            client = self._get_client()
            client.delete_object(Bucket=self._bucket, Key=s3_key)
            logger.info(f"Deleted from S3: {s3_key}")
            return True
        except Exception as exc:
            logger.error(f"S3 delete error for {s3_key!r}: {exc}")
            return False

    # ── Bucket connectivity test ──────────────────────────────────────
    def test_connection(self) -> dict:
        """
        Test if we can reach the S3 bucket.

        Returns:
            { "connected": bool, "bucket": str, "error": str }
        """
        if not self._configured:
            return {"connected": False, "bucket": "", "error": "S3_BUCKET_NAME not set"}

        try:
            client = self._get_client()
            client.head_bucket(Bucket=self._bucket)
            return {"connected": True, "bucket": self._bucket, "error": ""}
        except Exception as exc:
            error_str = str(exc)
            logger.warning(f"S3 connection test failed: {error_str}")
            return {"connected": False, "bucket": self._bucket, "error": error_str}
