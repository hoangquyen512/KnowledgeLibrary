from __future__ import annotations

import hashlib
import re
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings

_UNSAFE_CHARS = re.compile(r'[<>:"|?*\\/\x00-\x1f]')


def safe_object_filename(filename: str, *, max_stem: int = 40, fallback: str = "file") -> str:
    """Windows-safe short leaf name (keeps a short extension)."""
    raw = (filename or fallback).strip() or fallback
    name = Path(raw.replace("\\", "/")).name
    stem = _UNSAFE_CHARS.sub("_", Path(name).stem).strip(" .") or fallback
    suffix = Path(name).suffix[:20]
    if len(stem) > max_stem:
        stem = stem[:max_stem]
    return f"{stem}{suffix}"


class ObjectStorage:
    """MinIO/S3 when available; local filesystem fallback."""

    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self._local_root = Path(__file__).resolve().parents[2] / "data" / "object-store"
        self._use_local = settings.demo_mode or settings.app_env in ("development", "test")
        self._client = None
        if not self._use_local:
            try:
                self._client = boto3.client(
                    "s3",
                    endpoint_url=settings.s3_endpoint,
                    aws_access_key_id=settings.s3_access_key,
                    aws_secret_access_key=settings.s3_secret_key,
                    region_name=settings.s3_region,
                    config=Config(signature_version="s3v4"),
                )
                self._ensure_bucket()
            except Exception:  # noqa: BLE001
                self._use_local = True
                self._client = None

    def _ensure_bucket(self) -> None:
        assert self._client is not None
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self.bucket)

    def put_bytes(self, key: str, data: bytes, *, content_type: str) -> str:
        if self._use_local or self._client is None:
            path = self._local_root.joinpath(*key.replace("\\", "/").split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return key
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def get_bytes(self, key: str) -> bytes:
        if self._use_local or self._client is None:
            path = self._local_root.joinpath(*key.replace("\\", "/").split("/"))
            if not path.is_file():
                raise FileNotFoundError(key)
            return path.read_bytes()
        try:
            obj = self._client.get_object(Bucket=self.bucket, Key=key)
            return obj["Body"].read()
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise

    def exists(self, key: str) -> bool:
        if self._use_local or self._client is None:
            path = self._local_root.joinpath(*key.replace("\\", "/").split("/"))
            return path.is_file()
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete_prefix(self, prefix: str) -> int:
        """Best-effort delete all objects under prefix. Returns number removed."""
        prefix = prefix.replace("\\", "/").lstrip("/")
        removed = 0
        if self._use_local or self._client is None:
            root = self._local_root.joinpath(*prefix.split("/")) if prefix else self._local_root
            if root.is_file():
                root.unlink(missing_ok=True)
                return 1
            if root.is_dir():
                for path in sorted(root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink(missing_ok=True)
                        removed += 1
                    elif path.is_dir():
                        try:
                            path.rmdir()
                        except OSError:
                            pass
                try:
                    root.rmdir()
                except OSError:
                    pass
            return removed
        # S3/MinIO list + delete
        assert self._client is not None
        token: str | None = None
        while True:
            kwargs: dict = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = self._client.list_objects_v2(**kwargs)
            contents = resp.get("Contents") or []
            if contents:
                self._client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": o["Key"]} for o in contents]},
                )
                removed += len(contents)
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return removed

    @staticmethod
    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


def get_object_storage() -> ObjectStorage:
    return ObjectStorage()
