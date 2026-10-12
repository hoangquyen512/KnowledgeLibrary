from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _API_ROOT / ".env"


def _resolve_sqlite_url(url: str) -> str:
    if "sqlite" not in url:
        return url
    if url.startswith("sqlite+aiosqlite:///"):
        prefix, rest = "sqlite+aiosqlite:///", url[len("sqlite+aiosqlite:///") :]
    elif url.startswith("sqlite:///"):
        prefix, rest = "sqlite:///", url[len("sqlite:///") :]
    else:
        return url
    # Already absolute (Unix / or Windows drive letter).
    if rest.startswith("/") or (len(rest) >= 2 and rest[1] == ":"):
        return url
    abs_path = (_API_ROOT / rest.lstrip("./")).resolve()
    return f"{prefix}{abs_path.as_posix()}"


class Settings(BaseSettings):
    # Absolute .env path + ignore empty process env so blank GOOGLE_* from the
    # shell/start script cannot override values saved in apps/api/.env.
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_env: str = "development"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    api_public_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://knowledge:knowledge@localhost:5432/knowledge"
    database_url_sync: str = "postgresql://knowledge:knowledge@localhost:5432/knowledge"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "knowledge-library"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"

    app_encryption_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    session_secret: str = ""
    connector_signing_secret: str = ""

    embedding_model: str = "bge-m3"
    embedding_service_url: str = "http://localhost:8081"
    embedding_dimension: int = 1024
    gemini_model: str = "gemini-flash-latest"

    ask_hybrid_pool_size: int = 30
    ask_rerank_top_k: int = 8
    ask_query_rewrite_max_tokens: int = 4
    ask_rerank_timeout_seconds: float = 15.0
    max_upload_bytes: int = 50 * 1024 * 1024

    session_cookie_name: str = "kl_session"
    csrf_cookie_name: str = "kl_csrf"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_ttl_seconds: int = 60 * 60 * 24 * 7

    seed_super_admin_email: str = ""

    demo_mode: bool = False
    admin_storage_quota_bytes: int | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id.strip() and self.google_client_secret.strip())

    @model_validator(mode="after")
    def resolve_sqlite_paths(self) -> Self:
        self.database_url = _resolve_sqlite_url(self.database_url)
        self.database_url_sync = _resolve_sqlite_url(self.database_url_sync)
        return self

    def require_runtime_secrets(self) -> None:
        missing: list[str] = []
        if not self.session_secret or len(self.session_secret) < 32:
            missing.append("SESSION_SECRET (>=32 chars)")
        if self.is_production and not self.app_encryption_key:
            missing.append("APP_ENCRYPTION_KEY")
        if missing:
            raise RuntimeError(f"Missing required secrets: {', '.join(missing)}")


settings = Settings()
