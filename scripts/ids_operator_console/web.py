from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from fastapi import FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .alerts import (
    ALERT_TRIAGE_STATES,
    add_investigation_note,
    get_alert_timeline,
    list_alerts_for_triage,
    transition_alert_status,
)
from .auth import (
    current_admin,
    login_admin_with_password,
    logout_admin,
    require_authenticated_api,
    require_authenticated_redirect,
    validate_csrf_form,
)
from .config import OperatorConsoleConfig
from .db import DEFAULT_SENSOR_ID, OperatorStore


def _decode_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return dict(raw_payload)
    if isinstance(raw_payload, str):
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _format_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _prepare_health_snapshot(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    if not summaries:
        return {
            "status": "no-data",
            "summary_ts": None,
            "alert_count": 0,
            "anomaly_count": 0,
            "window_seconds": None,
            "source": {},
        }

    latest = dict(summaries[0])
    payload = _decode_payload(latest.get("payload_json"))
    return {
        "status": "ok",
        "summary_ts": latest.get("summary_ts"),
        "alert_count": payload.get("alert_count", 0),
        "anomaly_count": payload.get("anomaly_count", 0),
        "window_seconds": payload.get("window_seconds"),
        "source": payload,
    }


def _filter_by_sensor_id(items: list[dict[str, Any]], sensor_id: str) -> list[dict[str, Any]]:
    return [item for item in items if str(item.get("sensor_id", DEFAULT_SENSOR_ID)) == sensor_id]


def _with_decoded_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["payload"] = _decode_payload(item.get("payload_json"))
        hydrated.append(item)
    return hydrated


def _find_alert(store: OperatorStore, *, alert_id: int) -> dict[str, Any] | None:
    for alert in store.list_alerts(limit=500):
        if int(alert["id"]) == alert_id:
            hydrated = dict(alert)
            hydrated["payload"] = _decode_payload(hydrated.get("payload_json"))
            return hydrated
    return None


def create_operator_console_web_app(
    config: OperatorConsoleConfig,
    *,
    store: OperatorStore | None = None,
) -> FastAPI:
    config.ensure_runtime_dirs()
    if store is None:
        bootstrap_store = OperatorStore.open(config.database_path)
        bootstrap_store.close()
    templates = Jinja2Templates(directory=str(config.templates_dir))

    app = FastAPI(title="IDS Operator Console", version="0.2.0")
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key,
        session_cookie=config.session_cookie_name,
        https_only=False,
        same_site="lax",
    )
    app.state.operator_console_config = config
    app.state.templates = templates

    if config.static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(config.static_dir)), name="static")

    def _open_store() -> OperatorStore:
        return OperatorStore.open(config.database_path)

    def render_template(request: Request, template_name: str, **context: Any) -> HTMLResponse:
        template_context = {
            "request": request,
            "admin": current_admin(request),
            "triage_states": ALERT_TRIAGE_STATES,
            "generated_at": _format_utc_now(),
            **context,
        }
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=template_context,
        )

    @app.get("/", response_class=HTMLResponse)
    def root(request: Request) -> RedirectResponse:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request) -> Response:
        if current_admin(request) is not None:
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        return render_template(request, "login.html", login_error=None)

    @app.post("/login", response_class=HTMLResponse)
    async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ) -> Response:
        runtime_store = _open_store()
        try:
            admin = login_admin_with_password(
                request,
                store=runtime_store,
                username=username,
                password=password,
            )
        finally:
            runtime_store.close()
        if admin is None:
            return render_template(
                request,
                "login.html",
                login_error="Invalid username or password.",
            )
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    @app.post("/logout")
    async def logout_submit(
        request: Request,
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        logout_admin(request)
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request, status_filter: str | None = None) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect

        if status_filter is not None and status_filter not in ALERT_TRIAGE_STATES:
            raise HTTPException(status_code=400, detail="Invalid status filter")

        runtime_store = _open_store()
        try:
            alerts = list_alerts_for_triage(
                runtime_store,
                triage_status=status_filter,
                include_suppressed=True,
                limit=200,
            )
            anomalies = _with_decoded_payload(runtime_store.list_anomalies(limit=100))
            summaries = _with_decoded_payload(runtime_store.list_recent_summaries(limit=30))
        finally:
            runtime_store.close()
        health = _prepare_health_snapshot(summaries)
        return render_template(
            request,
            "dashboard.html",
            alerts=alerts,
            anomalies=anomalies,
            summaries=summaries,
            health=health,
            status_filter=status_filter,
        )

    @app.get("/alerts/{alert_id}", response_class=HTMLResponse)
    def alert_detail(request: Request, alert_id: int) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect

        runtime_store = _open_store()
        try:
            alert = _find_alert(runtime_store, alert_id=alert_id)
            if alert is None:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
            timeline = get_alert_timeline(runtime_store, alert_id=alert_id)
        finally:
            runtime_store.close()

        if alert is None:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        return render_template(
            request,
            "alert_detail.html",
            alert=alert,
            timeline=timeline,
        )

    @app.post("/alerts/{alert_id}/status")
    async def alert_update_status(
        request: Request,
        alert_id: int,
        to_status: str = Form(...),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        admin = require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            transition_alert_status(
                runtime_store,
                alert_id=alert_id,
                to_status=to_status,
                changed_by=admin.username,
            )
        finally:
            runtime_store.close()
        return RedirectResponse(url=f"/alerts/{alert_id}", status_code=status.HTTP_303_SEE_OTHER)

    @app.post("/alerts/{alert_id}/notes")
    async def alert_add_note(
        request: Request,
        alert_id: int,
        note_text: str = Form(...),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        admin = require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            add_investigation_note(
                runtime_store,
                alert_id=alert_id,
                note_text=note_text,
                author=admin.username,
            )
        finally:
            runtime_store.close()
        return RedirectResponse(url=f"/alerts/{alert_id}", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/anomalies", response_class=HTMLResponse)
    def anomalies_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            anomalies = _with_decoded_payload(runtime_store.list_anomalies(limit=200))
        finally:
            runtime_store.close()
        return render_template(request, "anomalies.html", anomalies=anomalies)

    @app.get("/reports", response_class=HTMLResponse)
    def reports_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            summaries = _with_decoded_payload(runtime_store.list_recent_summaries(limit=100))
        finally:
            runtime_store.close()
        return render_template(request, "reports.html", summaries=summaries)

    @app.get("/api/v1/console/snapshot", response_class=JSONResponse)
    def api_console_snapshot(
        request: Request,
        sensor_id: str = Query(DEFAULT_SENSOR_ID),
        include_suppressed: bool = Query(False),
    ) -> JSONResponse:
        require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            alerts = list_alerts_for_triage(
                runtime_store,
                include_suppressed=include_suppressed,
                limit=500,
            )
            alerts = _filter_by_sensor_id(alerts, sensor_id)
            anomalies = _filter_by_sensor_id(
                _with_decoded_payload(runtime_store.list_anomalies(limit=500)),
                sensor_id,
            )
            summaries = _filter_by_sensor_id(
                _with_decoded_payload(runtime_store.list_recent_summaries(limit=200)),
                sensor_id,
            )
        finally:
            runtime_store.close()
        return JSONResponse(
            {
                "sensor_id": sensor_id,
                "alerts": alerts,
                "anomalies": anomalies,
                "summaries": summaries,
            }
        )

    @app.get("/api/v1/alerts", response_class=JSONResponse)
    def api_alerts(
        request: Request,
        sensor_id: str = Query(DEFAULT_SENSOR_ID),
        triage_status: str | None = Query(None),
        include_suppressed: bool = Query(True),
    ) -> JSONResponse:
        require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            alerts = list_alerts_for_triage(
                runtime_store,
                triage_status=triage_status,
                include_suppressed=include_suppressed,
                limit=500,
            )
        finally:
            runtime_store.close()
        return JSONResponse({"sensor_id": sensor_id, "alerts": _filter_by_sensor_id(alerts, sensor_id)})

    @app.get("/api/v1/anomalies", response_class=JSONResponse)
    def api_anomalies(
        request: Request,
        sensor_id: str = Query(DEFAULT_SENSOR_ID),
    ) -> JSONResponse:
        require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            anomalies = _filter_by_sensor_id(
                _with_decoded_payload(runtime_store.list_anomalies(limit=500)),
                sensor_id,
            )
        finally:
            runtime_store.close()
        return JSONResponse({"sensor_id": sensor_id, "anomalies": anomalies})

    @app.get("/api/v1/summaries", response_class=JSONResponse)
    def api_summaries(
        request: Request,
        sensor_id: str = Query(DEFAULT_SENSOR_ID),
    ) -> JSONResponse:
        require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            summaries = _filter_by_sensor_id(
                _with_decoded_payload(runtime_store.list_recent_summaries(limit=300)),
                sensor_id,
            )
        finally:
            runtime_store.close()
        return JSONResponse({"sensor_id": sensor_id, "summaries": summaries})

    return app


__all__ = ["create_operator_console_web_app"]
