from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ids.console.auth import (  # noqa: E402
    ensure_admin_user,
    hash_password,
    login_admin_with_password,
    logout_admin,
    require_authenticated_api,
    require_authenticated_redirect,
    validate_csrf_form,
    verify_password,
)
from ids.console.db import OperatorStore  # noqa: E402


def _build_test_app(database_path: Path) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="auth-test-secret", session_cookie="ids_operator_session")

    @app.post("/login")
    async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ) -> JSONResponse:
        store = OperatorStore.open(database_path)
        try:
            admin = login_admin_with_password(request, store=store, username=username, password=password)
        finally:
            store.close()
        if admin is None:
            return JSONResponse({"ok": False}, status_code=401)
        return JSONResponse({"ok": True, "csrf_token": admin.csrf_token, "username": admin.username})

    @app.get("/console")
    async def console(request: Request):
        redirect = require_authenticated_redirect(request)
        if redirect is not None:
            return redirect
        admin = require_authenticated_api(request)
        return JSONResponse({"ok": True, "username": admin.username})

    @app.post("/console/note")
    async def post_note(
        request: Request,
        note: str = Form(...),
        csrf_token: str = Form(""),
    ) -> JSONResponse:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        admin = require_authenticated_api(request)
        return JSONResponse({"ok": True, "author": admin.username, "note": note})

    @app.post("/logout")
    async def logout(
        request: Request,
        csrf_token: str = Form(""),
    ) -> JSONResponse:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        logout_admin(request)
        return JSONResponse({"ok": True})

    return app


def test_password_hash_roundtrip() -> None:
    encoded = hash_password("super-secret-password")
    assert verify_password("super-secret-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_protected_route_redirects_and_invalid_login_fails_closed(tmp_path: Path) -> None:
    db_path = tmp_path / "operator_console.db"
    store = OperatorStore.open(db_path)
    try:
        ensure_admin_user(store, username="admin", password="correct-password")
        app = _build_test_app(db_path)
        client = TestClient(app)

        response = client.get("/console", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

        bad_login = client.post(
            "/login",
            data={"username": "admin", "password": "wrong-password"},
            follow_redirects=False,
        )
        assert bad_login.status_code == 401

        still_blocked = client.get("/console", follow_redirects=False)
        assert still_blocked.status_code == 303
        assert still_blocked.headers["location"] == "/login"
    finally:
        store.close()


def test_valid_login_persists_session_and_csrf_is_enforced_for_form_posts(tmp_path: Path) -> None:
    db_path = tmp_path / "operator_console.db"
    store = OperatorStore.open(db_path)
    try:
        ensure_admin_user(store, username="admin", password="correct-password")
        app = _build_test_app(db_path)
        client = TestClient(app)

        login = client.post(
            "/login",
            data={"username": "admin", "password": "correct-password"},
            follow_redirects=False,
        )
        assert login.status_code == 200
        csrf_token = login.json()["csrf_token"]

        console = client.get("/console")
        assert console.status_code == 200
        assert console.json()["username"] == "admin"

        missing_csrf = client.post("/console/note", data={"note": "triage update"})
        assert missing_csrf.status_code == 403

        bad_csrf = client.post(
            "/console/note",
            data={"note": "triage update", "csrf_token": "bad-token"},
        )
        assert bad_csrf.status_code == 403

        ok_csrf = client.post(
            "/console/note",
            data={"note": "triage update", "csrf_token": csrf_token},
        )
        assert ok_csrf.status_code == 200
        assert ok_csrf.json()["author"] == "admin"

        logout = client.post("/logout", data={"csrf_token": csrf_token})
        assert logout.status_code == 200

        post_logout = client.get("/console", follow_redirects=False)
        assert post_logout.status_code == 303
        assert post_logout.headers["location"] == "/login"
    finally:
        store.close()
