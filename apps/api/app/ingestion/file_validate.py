"""Upload validation: extension, MIME, size, magic signatures."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.models.source import SourceType

# Default max size; override via settings.max_upload_bytes when configured.
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\- ()\[\]]+")


@dataclass(frozen=True)
class FileTypeSpec:
    source_type: str
    extensions: frozenset[str]
    mime_types: frozenset[str]
    # magic prefixes (first bytes); empty means skip signature check
    signatures: tuple[bytes, ...]


FILE_SPECS: dict[str, FileTypeSpec] = {
    SourceType.FILE_EXCEL: FileTypeSpec(
        source_type=SourceType.FILE_EXCEL,
        extensions=frozenset({".xlsx", ".xls"}),
        mime_types=frozenset(
            {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
                "application/octet-stream",
            }
        ),
        signatures=(b"PK\x03\x04", b"\xd0\xcf\x11\xe0"),  # zip / OLE
    ),
    SourceType.FILE_CSV: FileTypeSpec(
        source_type=SourceType.FILE_CSV,
        extensions=frozenset({".csv"}),
        mime_types=frozenset(
            {"text/csv", "application/csv", "text/plain", "application/octet-stream"}
        ),
        signatures=(),
    ),
    SourceType.FILE_WORD: FileTypeSpec(
        source_type=SourceType.FILE_WORD,
        extensions=frozenset({".docx"}),
        mime_types=frozenset(
            {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/octet-stream",
            }
        ),
        signatures=(b"PK\x03\x04",),
    ),
    SourceType.FILE_POWERPOINT: FileTypeSpec(
        source_type=SourceType.FILE_POWERPOINT,
        extensions=frozenset({".pptx"}),
        mime_types=frozenset(
            {
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "application/octet-stream",
            }
        ),
        signatures=(b"PK\x03\x04",),
    ),
    SourceType.FILE_PDF: FileTypeSpec(
        source_type=SourceType.FILE_PDF,
        extensions=frozenset({".pdf"}),
        mime_types=frozenset({"application/pdf", "application/octet-stream"}),
        signatures=(b"%PDF",),
    ),
}

_EXT_TO_SOURCE: dict[str, str] = {}
for _spec in FILE_SPECS.values():
    for _ext in _spec.extensions:
        _EXT_TO_SOURCE[_ext] = _spec.source_type

# Blocked extensions (executables / archives)
BLOCKED_EXTENSIONS = frozenset(
    {
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".msi",
        ".scr",
        ".js",
        ".vbs",
        ".ps1",
        ".sh",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".dll",
        ".so",
        ".dmg",
        ".iso",
    }
)


def sanitize_filename(name: str) -> str:
    base = (name or "file").replace("\\", "/").split("/")[-1].strip()
    base = _SAFE_NAME.sub("_", base)
    return (base or "file")[:400]


def detect_source_type(filename: str) -> str | None:
    lower = filename.lower()
    for ext, stype in _EXT_TO_SOURCE.items():
        if lower.endswith(ext):
            return stype
    return None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_upload(
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    expected_source_type: str | None = None,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> tuple[str, str]:
    """Return (source_type, sanitized_filename). Raises HTTPException on failure."""
    safe_name = sanitize_filename(filename)
    lower = safe_name.lower()
    for blocked in BLOCKED_EXTENSIONS:
        if lower.endswith(blocked):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "message": f"File type {blocked} is not allowed.",
                },
            )

    source_type = detect_source_type(safe_name)
    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": "Supported types: .xlsx, .xls, .csv, .docx, .pptx, .pdf",
            },
        )
    if expected_source_type:
        # Excel/CSV card accepts both spreadsheet kinds.
        spreadsheet = {SourceType.FILE_EXCEL, SourceType.FILE_CSV}
        if expected_source_type in spreadsheet and source_type in spreadsheet:
            pass
        elif expected_source_type != source_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "message": f"Expected {expected_source_type} but got {source_type}.",
                },
            )

    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"File exceeds max size of {max_bytes // (1024 * 1024)} MB.",
            },
        )
    if len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "FILE_CORRUPTED", "message": "File is empty."},
        )

    spec = FILE_SPECS[source_type]
    mime = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if mime and mime not in spec.mime_types and mime != "application/octet-stream":
        if spec.signatures and not any(data.startswith(sig) for sig in spec.signatures):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "message": f"MIME type {mime} is not allowed for this file.",
                },
            )

    if spec.signatures and not any(data.startswith(sig) for sig in spec.signatures):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "FILE_CORRUPTED",
                "message": "File signature does not match the declared type.",
            },
        )

    return source_type, safe_name
