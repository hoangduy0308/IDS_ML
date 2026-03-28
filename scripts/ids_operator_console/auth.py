from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_bytes, token_urlsafe
from typing import Mapping
import binascii

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse

from .db import OperatorStore


PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 390_000

SESSION_AUTHENTICATED_KEY = "auth.authenticated"
SESSION_USERNAME_KEY = "auth.username"
SESSION_CSRF_TOKEN_KEY = "auth.csrf_token"
SESSION_CREATED_AT_KEY = "auth.created_at"


@dataclass(frozen=True)
class AuthenticatedAdmin:
    username: str
    csrf_token: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _require_session(request: Request) -> dict:
    try:
        session = request.session
    except AssertionError as exc:
        raise RuntimeError("SessionMiddleware is required for operator auth helpers") from exc
    return session


def hash_password(
    password: str,
    *,
    salt: bytes | None = None,
    iterations: int = PASSWORD_HASH_ITERATIONS,
) -> str:
    if not password:
        raise ValueError("password must not be blank")
    if iterations < 120_000:
        raise ValueError("iterations must be >= 120000")

    salt_bytes = salt or token_bytes(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    return f"{PASSWORD_HASH_SCHEME}${iterations}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        scheme, raw_iterations, raw_salt, raw_digest = encoded_hash.split("$", 3)
    except ValueError:
        return False

    if scheme != PASSWORD_HASH_SCHEME:
        return False

    try:
        iterations = int(raw_iterations)
        salt = binascii.unhexlify(raw_salt.encode("ascii"))
        expected_digest = binascii.unhexlify(raw_digest.encode("ascii"))
    except (ValueError, binascii.Error):
        return False

    candidate = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return compare_digest(candidate, expected_digest)


def ensure_admin_user(
    store: OperatorStore,
    *,
    username: str,
    password: str,
    is_active: bool = True,
) -> dict:
    return store.upsert_admin_user(
        username=username,
        password_hash=hash_password(password),
        is_active=is_active,
    )


def verify_admin_credentials(
    store: OperatorStore,
    *,
    username: str,
    password: str,
) -> bool:
    user = store.get_admin_user(username)
    if user is None:
        return False
    if int(user.get("is_active", 0)) != 1:
        return False

    password_hash = str(user.get("password_hash", ""))
    if not verify_password(password, password_hash):
        return False

    store.upsert_admin_user(
        username=username,
        password_hash=password_hash,
        is_active=True,
        last_login_at=_utc_now_iso(),
    )
    return True


def establish_admin_session(request: Request, *, username: str) -> AuthenticatedAdmin:
    session = _require_session(request)
    csrf_token = token_urlsafe(24)
    session.clear()
    session[SESSION_AUTHENTICATED_KEY] = True
    session[SESSION_USERNAME_KEY] = username
    session[SESSION_CSRF_TOKEN_KEY] = csrf_token
    session[SESSION_CREATED_AT_KEY] = _utc_now_iso()
    return AuthenticatedAdmin(username=username, csrf_token=csrf_token)


def login_admin_with_password(
    request: Request,
    *,
    store: OperatorStore,
    username: str,
    password: str,
) -> AuthenticatedAdmin | None:
    if not verify_admin_credentials(store, username=username, password=password):
        return None
    return establish_admin_session(request, username=username)


def current_admin(request: Request) -> AuthenticatedAdmin | None:
    session = _require_session(request)
    authenticated = bool(session.get(SESSION_AUTHENTICATED_KEY, False))
    username = session.get(SESSION_USERNAME_KEY)
    csrf_token = session.get(SESSION_CSRF_TOKEN_KEY)
    if not authenticated or not isinstance(username, str) or not isinstance(csrf_token, str):
        return None
    return AuthenticatedAdmin(username=username, csrf_token=csrf_token)


def require_authenticated_redirect(
    request: Request,
    *,
    login_path: str = "/login",
) -> RedirectResponse | None:
    if current_admin(request) is not None:
        return None
    return RedirectResponse(url=login_path, status_code=status.HTTP_303_SEE_OTHER)


def require_authenticated_api(request: Request) -> AuthenticatedAdmin:
    admin = current_admin(request)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return admin


def validate_csrf_token(request: Request, provided_token: str | None) -> None:
    admin = require_authenticated_api(request)
    if not provided_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing CSRF token",
        )
    if not compare_digest(admin.csrf_token, provided_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


def validate_csrf_form(
    request: Request,
    form_data: Mapping[str, str],
    *,
    field_name: str = "csrf_token",
) -> None:
    provided = form_data.get(field_name)
    validate_csrf_token(request, provided)


def logout_admin(request: Request) -> None:
    session = _require_session(request)
    session.clear()

