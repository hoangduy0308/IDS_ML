from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse
import os


DEFAULT_ENVIRONMENT = "development"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_RELOAD = False
DEFAULT_LOG_LEVEL = "info"
DEFAULT_SESSION_COOKIE_NAME = "ids_operator_session"
DEFAULT_SESSION_COOKIE_SAME_SITE = "lax"
DEFAULT_SESSION_MAX_AGE_SECONDS = 43_200
DEFAULT_FORWARDED_ALLOW_IPS = "127.0.0.1"

PLACEHOLDER_SECRET_VALUES = {"change-me", "replace-me", "unsafe-dev-secret"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_bool(raw: str, *, name: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean-like value, got {raw!r}")


def _parse_port(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"IDS_OPERATOR_CONSOLE_PORT must be an integer, got {raw!r}") from exc
    if value < 1 or value > 65535:
        raise ValueError(f"IDS_OPERATOR_CONSOLE_PORT must be between 1 and 65535, got {value}")
    return value


def _parse_positive_int(raw: str, *, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value < 1:
        raise ValueError(f"{name} must be >= 1, got {value}")
    return value


def _resolve_path(raw: str, *, root: Path) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _clean_optional(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = raw.strip()
    return normalized or None


def _normalize_environment(raw: str) -> str:
    normalized = raw.strip().lower()
    if normalized not in {"development", "test", "production"}:
        raise ValueError(
            "IDS_OPERATOR_CONSOLE_ENVIRONMENT must be one of: development, test, production"
        )
    return normalized


def _normalize_root_path(raw: str | None) -> str:
    if raw is None:
        return ""
    normalized = raw.strip()
    if not normalized or normalized == "/":
        return ""
    if not normalized.startswith("/"):
        raise ValueError("IDS_OPERATOR_CONSOLE_ROOT_PATH must start with '/'")
    return normalized.rstrip("/")


def _normalize_same_site(raw: str) -> str:
    normalized = raw.strip().lower()
    if normalized not in {"lax", "strict", "none"}:
        raise ValueError(
            "IDS_OPERATOR_CONSOLE_SESSION_COOKIE_SAME_SITE must be one of: lax, strict, none"
        )
    return normalized


def _read_secret_from_file(secret_path: Path, *, env_name: str) -> str:
    if not secret_path.is_file():
        raise FileNotFoundError(f"{env_name} file not found: {secret_path}")
    value = secret_path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"{env_name} file must not be blank: {secret_path}")
    return value


def _load_secret(
    env: Mapping[str, str],
    *,
    value_name: str,
    file_name: str,
    root: Path,
    default: str | None = None,
) -> tuple[str | None, Path | None]:
    raw_value = _clean_optional(env.get(value_name))
    raw_file = _clean_optional(env.get(file_name))
    if raw_value is not None and raw_file is not None:
        raise ValueError(f"Only one of {value_name} or {file_name} may be set")
    if raw_file is not None:
        resolved_file = _resolve_path(raw_file, root=root)
        return _read_secret_from_file(resolved_file, env_name=file_name), resolved_file
    if raw_value is not None:
        return raw_value, None
    return default, None


def _parse_public_base_url(raw: str | None, *, root_path: str) -> str | None:
    value = _clean_optional(raw)
    if value is None:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL must be an absolute http(s) URL"
        )
    path = parsed.path.rstrip("/")
    normalized_root = root_path or ""
    if path and path != normalized_root:
        raise ValueError(
            "IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL path must match IDS_OPERATOR_CONSOLE_ROOT_PATH"
        )
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(
            "IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL must not include params, query, or fragment"
        )
    normalized_path = normalized_root or ""
    return f"{parsed.scheme}://{parsed.netloc}{normalized_path}"


@dataclass(frozen=True)
class OperatorConsoleConfig:
    environment: str
    host: str
    port: int
    reload: bool
    log_level: str
    secret_key: str
    secret_key_source: Path | None
    session_cookie_name: str
    session_cookie_same_site: str
    session_cookie_https_only: bool
    session_cookie_domain: str | None
    session_cookie_path: str
    session_max_age_seconds: int
    forwarded_allow_ips: str
    root_path: str
    public_base_url: str | None
    database_path: Path
    alerts_input_path: Path
    quarantine_input_path: Path
    summary_input_path: Path
    templates_dir: Path
    static_dir: Path
    telegram_bot_token: str | None
    telegram_bot_token_source: Path | None
    telegram_chat_id: str | None

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("host must not be blank")
        if self.port < 1 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")
        if not self.secret_key.strip():
            raise ValueError("secret_key must not be blank")
        if not self.session_cookie_name.strip():
            raise ValueError("session_cookie_name must not be blank")
        if not self.session_cookie_path.startswith("/"):
            raise ValueError("session_cookie_path must start with '/'")
        if self.session_max_age_seconds < 1:
            raise ValueError("session_max_age_seconds must be >= 1")
        if not self.forwarded_allow_ips.strip():
            raise ValueError("forwarded_allow_ips must not be blank")
        if self.environment == "production":
            if self.secret_key.strip() in PLACEHOLDER_SECRET_VALUES:
                raise ValueError("production secret_key must not use a placeholder value")
            if not self.session_cookie_https_only:
                raise ValueError("production session cookies must require HTTPS")
            if self.public_base_url is None:
                raise ValueError("production requires IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("production public_base_url must use https")
        if self.session_cookie_same_site == "none" and not self.session_cookie_https_only:
            raise ValueError("SameSite=None cookies must also require HTTPS")
        if (self.telegram_bot_token is None) != (self.telegram_chat_id is None):
            raise ValueError(
                "telegram_bot_token and telegram_chat_id must be set together or both omitted"
            )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def external_root_path(self) -> str:
        return self.root_path or ""

    def ensure_runtime_dirs(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


def load_operator_console_config(
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
) -> OperatorConsoleConfig:
    env = dict(os.environ if environ is None else environ)
    root = (repo_root or _repo_root()).resolve()

    environment = _normalize_environment(
        env.get("IDS_OPERATOR_CONSOLE_ENVIRONMENT", DEFAULT_ENVIRONMENT)
    )
    host = env.get("IDS_OPERATOR_CONSOLE_HOST", DEFAULT_HOST).strip()
    port = _parse_port(env["IDS_OPERATOR_CONSOLE_PORT"]) if "IDS_OPERATOR_CONSOLE_PORT" in env else DEFAULT_PORT
    reload = (
        _parse_bool(env["IDS_OPERATOR_CONSOLE_RELOAD"], name="IDS_OPERATOR_CONSOLE_RELOAD")
        if "IDS_OPERATOR_CONSOLE_RELOAD" in env
        else DEFAULT_RELOAD
    )
    log_level = env.get("IDS_OPERATOR_CONSOLE_LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().lower()
    root_path = _normalize_root_path(env.get("IDS_OPERATOR_CONSOLE_ROOT_PATH"))
    public_base_url = _parse_public_base_url(
        env.get("IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL"),
        root_path=root_path,
    )
    session_cookie_path = env.get("IDS_OPERATOR_CONSOLE_SESSION_COOKIE_PATH", root_path or "/").strip() or "/"
    session_cookie_https_only_default = environment == "production"
    session_cookie_https_only = (
        _parse_bool(
            env["IDS_OPERATOR_CONSOLE_SESSION_COOKIE_HTTPS_ONLY"],
            name="IDS_OPERATOR_CONSOLE_SESSION_COOKIE_HTTPS_ONLY",
        )
        if "IDS_OPERATOR_CONSOLE_SESSION_COOKIE_HTTPS_ONLY" in env
        else session_cookie_https_only_default
    )
    session_cookie_same_site = _normalize_same_site(
        env.get(
            "IDS_OPERATOR_CONSOLE_SESSION_COOKIE_SAME_SITE",
            DEFAULT_SESSION_COOKIE_SAME_SITE,
        )
    )
    session_cookie_domain = _clean_optional(env.get("IDS_OPERATOR_CONSOLE_SESSION_COOKIE_DOMAIN"))
    session_max_age_seconds = (
        _parse_positive_int(
            env["IDS_OPERATOR_CONSOLE_SESSION_MAX_AGE_SECONDS"],
            name="IDS_OPERATOR_CONSOLE_SESSION_MAX_AGE_SECONDS",
        )
        if "IDS_OPERATOR_CONSOLE_SESSION_MAX_AGE_SECONDS" in env
        else DEFAULT_SESSION_MAX_AGE_SECONDS
    )
    forwarded_allow_ips = env.get(
        "IDS_OPERATOR_CONSOLE_FORWARDED_ALLOW_IPS",
        DEFAULT_FORWARDED_ALLOW_IPS,
    ).strip()

    secret_key, secret_key_source = _load_secret(
        env,
        value_name="IDS_OPERATOR_CONSOLE_SECRET_KEY",
        file_name="IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE",
        root=root,
        default="change-me",
    )
    telegram_bot_token, telegram_bot_token_source = _load_secret(
        env,
        value_name="IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN",
        file_name="IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE",
        root=root,
        default=None,
    )

    database_path = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_DATABASE_PATH", "artifacts/operator_console/operator_console.db"),
        root=root,
    )
    alerts_input_path = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_ALERTS_INPUT_PATH", "ids_live_alerts.jsonl"),
        root=root,
    )
    quarantine_input_path = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_QUARANTINE_INPUT_PATH", "ids_live_quarantine.jsonl"),
        root=root,
    )
    summary_input_path = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH", "ids_live_sensor_summary.jsonl"),
        root=root,
    )
    templates_dir = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_TEMPLATES_DIR", "ids/console/templates"),
        root=root,
    )
    static_dir = _resolve_path(
        env.get("IDS_OPERATOR_CONSOLE_STATIC_DIR", "ids/console/static"),
        root=root,
    )

    return OperatorConsoleConfig(
        environment=environment,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        secret_key=secret_key or "",
        secret_key_source=secret_key_source,
        session_cookie_name=env.get(
            "IDS_OPERATOR_CONSOLE_SESSION_COOKIE_NAME",
            DEFAULT_SESSION_COOKIE_NAME,
        ),
        session_cookie_same_site=session_cookie_same_site,
        session_cookie_https_only=session_cookie_https_only,
        session_cookie_domain=session_cookie_domain,
        session_cookie_path=session_cookie_path,
        session_max_age_seconds=session_max_age_seconds,
        forwarded_allow_ips=forwarded_allow_ips,
        root_path=root_path,
        public_base_url=public_base_url,
        database_path=database_path,
        alerts_input_path=alerts_input_path,
        quarantine_input_path=quarantine_input_path,
        summary_input_path=summary_input_path,
        templates_dir=templates_dir,
        static_dir=static_dir,
        telegram_bot_token=telegram_bot_token,
        telegram_bot_token_source=telegram_bot_token_source,
        telegram_chat_id=_clean_optional(env.get("IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID")),
    )
