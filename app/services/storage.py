from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.config import settings


class MediaStorage:
    def __init__(self) -> None:
        self.backend = settings.storage_backend.lower()

    async def persist_local_path(self, local_path: str, object_key: str | None = None) -> str:
        if self.backend != "s3":
            return local_path
        try:
            import boto3
        except Exception:
            logger.warning("S3 storage selected but boto3 is not installed; keeping local path")
            return local_path

        key = object_key or Path(local_path).as_posix()
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        try:
            client.upload_file(local_path, settings.s3_bucket, key)
            if settings.s3_public_base_url:
                return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
            return f"s3://{settings.s3_bucket}/{key}"
        except Exception as exc:
            logger.warning("S3 upload failed for {}: {}; keeping local path", local_path, exc)
            return local_path


media_storage = MediaStorage()
