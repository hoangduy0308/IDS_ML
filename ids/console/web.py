from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

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
from .reporting import build_report_bundle, build_report_rollup
from .auth import (
    current_admin,
    login_admin_with_password,
    logout_admin,
    require_authenticated_api,
    require_authenticated_redirect,
    validate_csrf_form,
)
from .config import OperatorConsoleConfig
from .db import ALLOWED_SETTING_KEYS, DEFAULT_SENSOR_ID, OperatorStore, open_existing_operator_store

# Setting key constants (sourced from ALLOWED_SETTING_KEYS in db.py)
SETTING_TELEGRAM_BOT_TOKEN = "telegram_bot_token"
SETTING_TELEGRAM_CHAT_ID = "telegram_chat_id"
from .health import build_liveness_payload, build_readiness_payload
from .migrations import assert_runtime_ready
from .notification_runtime import resolve_telegram_config, resolve_telegram_config_with_source
from .notifications import TelegramNotifierConfig

TRIAGE_LABELS = {
    "new": "New",
    "acknowledged": "Acknowledged",
    "investigating": "Investigating",
    "resolved": "Resolved",
    "false_positive": "False Positive",
}

SEVERITY_LABELS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "unknown": "Unknown",
}

STATE_LABELS = {
    "ok": "OK",
    "ready": "Ready",
    "disabled": "Disabled",
    "degraded": "Degraded",
    "no-data": "No Data",
    "unknown": "Unknown",
    "current": "Current",
    "active": "Active",
    "none": "None",
    "compatible": "Compatible",
}

PRIMARY_NAV = [
    {"key": "overview", "label": "Overview", "href": "/overview"},
    {"key": "alerts", "label": "Alerts", "href": "/alerts"},
    {"key": "operations", "label": "Operations", "href": "/operations"},
    {"key": "reports", "label": "Reports", "href": "/reports"},
    {"key": "live-logs", "label": "Live Logs", "href": "/live-logs"},
    {"key": "suppression-rules", "label": "Suppression Rules", "href": "/suppression-rules"},
    {"key": "system-health", "label": "System Health", "href": "/system-health"},
    {"key": "settings", "label": "Settings", "href": "/settings"},
]


def _mask_token(token: str) -> str:
    if len(token) <= 4:
        return "****"
    return "\u2022" * 6 + token[-4:]


def _format_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _filter_by_sensor_id(items: list[dict[str, Any]], sensor_id: str) -> list[dict[str, Any]]:
    return [item for item in items if str(item.get("sensor_id", DEFAULT_SENSOR_ID)) == sensor_id]


def _env_telegram_fallback(config: OperatorConsoleConfig) -> TelegramNotifierConfig | None:
    """Build env-backed Telegram config if both token and chat_id are set."""
    if config.telegram_bot_token and config.telegram_chat_id:
        return TelegramNotifierConfig(
            bot_token=config.telegram_bot_token,
            default_chat_id=config.telegram_chat_id,
        )
    return None


def _with_decoded_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import json

    hydrated: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw = item.get("payload_json")
        if isinstance(raw, dict):
            item["payload"] = dict(raw)
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                item["payload"] = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                item["payload"] = {}
        else:
            item["payload"] = {}
        hydrated.append(item)
    return hydrated


def create_operator_console_web_app(
    config: OperatorConsoleConfig,
    *,
    store: OperatorStore | None = None,
) -> FastAPI:
    runtime_inspection = assert_runtime_ready(config.database_path)
    templates = Jinja2Templates(directory=str(config.templates_dir))

    app = FastAPI(
        title="IDS Operator Console",
        version="0.4.0",
        root_path=config.root_path,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key,
        session_cookie=config.session_cookie_name,
        max_age=config.session_max_age_seconds,
        same_site=config.session_cookie_same_site,
        https_only=config.session_cookie_https_only,
        domain=config.session_cookie_domain,
        path=config.session_cookie_path,
    )
    app.state.operator_console_config = config
    app.state.operator_console_runtime_inspection = runtime_inspection
    app.state.templates = templates

    if config.static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(config.static_dir)), name="static")

    def _open_store() -> OperatorStore:
        if store is not None:
            return store
        return open_existing_operator_store(config.database_path)

    def render_template(request: Request, template_name: str, **context: Any) -> HTMLResponse:
        admin = current_admin(request)

        def _csrf_token() -> str:
            return admin.csrf_token if admin is not None else ""

        template_context: dict[str, Any] = {
            "request": request,
            "admin": admin,
            "csrf_token": _csrf_token,
            "triage_states": ALERT_TRIAGE_STATES,
            "triage_labels": TRIAGE_LABELS,
            "severity_labels": SEVERITY_LABELS,
            "state_labels": STATE_LABELS,
            "generated_at": _format_utc_now(),
            "public_base_url": config.public_base_url,
            "primary_nav": PRIMARY_NAV,
            "root_path": config.root_path,
            **context,
        }
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=template_context,
        )

    # ── Public routes ────────────────────────────────────────────────────────

    @app.get("/healthz", response_class=JSONResponse)
    def healthz(request: Request) -> JSONResponse:
        include_sensitive = current_admin(request) is not None
        return JSONResponse(
            build_liveness_payload(config, include_sensitive=include_sensitive)
        )

    @app.get("/readyz", response_class=JSONResponse)
    def readyz(request: Request) -> JSONResponse:
        include_sensitive = current_admin(request) is not None
        payload = build_readiness_payload(config, include_sensitive=include_sensitive)
        status_code = status.HTTP_200_OK if payload["ready"] else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(payload, status_code=status_code)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request) -> Response:
        if current_admin(request) is not None:
            return RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)
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
            if store is None:
                runtime_store.close()
        if admin is None:
            return render_template(
                request,
                "login.html",
                login_error="Invalid username or password.",
            )
        return RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)

    # ── Authenticated routes ─────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    def root(request: Request) -> RedirectResponse:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        return RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)

    @app.post("/logout")
    async def logout_submit(
        request: Request,
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        logout_admin(request)
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # ── Legacy redirects (must survive for bookmarks) ────────────────────────

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard_redirect(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        return RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/anomalies", response_class=HTMLResponse)
    def anomalies_redirect(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        return RedirectResponse(url="/operations", status_code=status.HTTP_303_SEE_OTHER)

    # ── Phase 2 HTML routes (not yet implemented — return 501) ───────────────

    @app.get("/overview", response_class=HTMLResponse)
    def overview_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            readiness = build_readiness_payload(config, include_sensitive=True)
            alert_preview = runtime_store.list_alerts(limit=8)
            anomaly_preview = runtime_store.list_anomalies(limit=8)
        finally:
            if store is None:
                runtime_store.close()
        return render_template(
            request,
            "overview.html",
            readiness=readiness,
            alert_preview=alert_preview,
            anomaly_preview=anomaly_preview,
        )

    @app.get("/alerts", response_class=HTMLResponse)
    def alerts_page(
        request: Request,
        status_filter: str | None = Query(None, alias="status"),
    ) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            alerts = list_alerts_for_triage(
                runtime_store,
                limit=200,
                triage_status=status_filter,
                include_suppressed=True,
            )
        finally:
            if store is None:
                runtime_store.close()
        return render_template(
            request,
            "alerts.html",
            alerts=alerts,
            status_filter=status_filter,
        )

    @app.get("/alerts/{alert_id}", response_class=HTMLResponse)
    def alert_detail(request: Request, alert_id: int) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            all_alerts = list_alerts_for_triage(
                runtime_store,
                limit=10000,
                include_suppressed=True,
            )
            alert = next((a for a in all_alerts if a["id"] == alert_id), None)
            if alert is None:
                raise HTTPException(status_code=404, detail="Alert not found")
            timeline = get_alert_timeline(runtime_store, alert_id=alert_id)
        finally:
            if store is None:
                runtime_store.close()
        return render_template(
            request,
            "alert_detail.html",
            alert=alert,
            family=alert.get("family", {}),
            notes=timeline["notes"],
            status_history=timeline["status_history"],
        )

    @app.post("/alerts/{alert_id}/notes")
    async def alert_add_note(
        request: Request,
        alert_id: int,
        csrf_token: str = Form(""),
        note_text: str = Form(""),
    ) -> Response:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        admin = require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            add_investigation_note(
                runtime_store,
                alert_id=alert_id,
                note_text=note_text,
                author=admin.username if admin else "unknown",
            )
        finally:
            if store is None:
                runtime_store.close()
        return RedirectResponse(
            url=f"/alerts/{alert_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/alerts/{alert_id}/status")
    async def alert_update_status(
        request: Request,
        alert_id: int,
        csrf_token: str = Form(""),
        new_status: str = Form(""),
    ) -> Response:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        admin = require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            transition_alert_status(
                runtime_store,
                alert_id=alert_id,
                to_status=new_status,
                changed_by=admin.username if admin else "unknown",
            )
        finally:
            if store is None:
                runtime_store.close()
        return RedirectResponse(
            url=f"/alerts/{alert_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.get("/operations", response_class=HTMLResponse)
    def operations_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            readiness = build_readiness_payload(config, include_sensitive=True)
            anomalies = runtime_store.list_anomalies(limit=200)
        finally:
            if store is None:
                runtime_store.close()
        return render_template(
            request,
            "operations.html",
            readiness=readiness,
            anomalies=anomalies,
        )

    @app.get("/reports", response_class=HTMLResponse)
    def reports_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            report_bundle = build_report_bundle(runtime_store)
            rollup = build_report_rollup(report_bundle)
            summaries = runtime_store.list_recent_summaries(limit=200)
        finally:
            if store is None:
                runtime_store.close()
        return render_template(
            request,
            "reports.html",
            rollup=rollup,
            summaries=summaries,
        )

    # ── Phase 3 HTML routes (not yet implemented — return 501) ───────────────

    @app.get("/live-logs", response_class=HTMLResponse)
    def live_logs_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            alerts = list_alerts_for_triage(runtime_store, limit=50, include_suppressed=True)
            anomalies = runtime_store.list_anomalies(limit=50)
        finally:
            if store is None:
                runtime_store.close()
        return render_template(request, "live_logs.html", alerts=alerts, anomalies=anomalies)

    @app.get("/suppression-rules", response_class=HTMLResponse)
    def suppression_rules_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            rules = runtime_store.list_active_suppression_rules(sensor_id=DEFAULT_SENSOR_ID)
        finally:
            if store is None:
                runtime_store.close()
        return render_template(request, "suppression_rules.html", rules=rules)

    @app.post("/suppression-rules")
    async def suppression_rules_create(
        request: Request,
        csrf_token: str = Form(""),
        rule_name: str = Form(""),
        match_field: str = Form(""),
        match_value: str = Form(""),
        applies_to: str = Form("model_alert"),
    ) -> Response:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            runtime_store.create_suppression_rule(
                rule_name=rule_name,
                match_field=match_field,
                match_value=match_value,
                applies_to=applies_to,
                sensor_id=DEFAULT_SENSOR_ID,
            )
        finally:
            if store is None:
                runtime_store.close()
        return RedirectResponse(url="/suppression-rules", status_code=status.HTTP_303_SEE_OTHER)

    @app.post("/suppression-rules/{rule_id}/deactivate")
    async def suppression_rule_deactivate(
        request: Request,
        rule_id: int,
        csrf_token: str = Form(""),
    ) -> Response:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            deactivated = runtime_store.deactivate_suppression_rule(rule_id=rule_id)
        finally:
            if store is None:
                runtime_store.close()
        if not deactivated:
            raise HTTPException(status_code=404, detail="Rule not found")
        return RedirectResponse(url="/suppression-rules", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/system-health", response_class=HTMLResponse)
    def system_health_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        readiness = build_readiness_payload(config, include_sensitive=True)
        return render_template(request, "system_health.html", readiness=readiness)

    # ── Settings routes ─────────────────────────────────────────────────────

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request) -> Response:
        redirect = require_authenticated_redirect(request, login_path="/login")
        if redirect is not None:
            return redirect
        runtime_store = _open_store()
        try:
            env_fallback = _env_telegram_fallback(config)
            effective, config_source = resolve_telegram_config_with_source(
                runtime_store, env_fallback,
            )
        finally:
            if store is None:
                runtime_store.close()

        # Derive display values from the resolved config
        if effective is not None:
            display_token = effective.bot_token
            display_chat_id = effective.default_chat_id
        else:
            display_token = ""
            display_chat_id = ""

        masked = _mask_token(display_token) if display_token.strip() else ""
        configured = effective is not None
        return render_template(
            request,
            "settings.html",
            masked_token=masked,
            chat_id=display_chat_id,
            configured=configured,
            config_source=config_source,
        )

    @app.post("/settings")
    async def settings_save(
        request: Request,
        csrf_token: str = Form(""),
        bot_token: str = Form(""),
        chat_id: str = Form(""),
    ) -> Response:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            stripped_token = bot_token.strip()
            stripped_chat_id = chat_id.strip()
            if not stripped_chat_id:
                # Clear both — empty chat_id means "disable DB Telegram config"
                runtime_store.set_setting(SETTING_TELEGRAM_BOT_TOKEN, "")
                runtime_store.set_setting(SETTING_TELEGRAM_CHAT_ID, "")
            else:
                # Only overwrite token if user typed a new one (password field
                # submits empty when unchanged — preserving the existing token)
                existing_token = runtime_store.get_setting(SETTING_TELEGRAM_BOT_TOKEN) or ""
                if stripped_token:
                    runtime_store.set_setting(SETTING_TELEGRAM_BOT_TOKEN, stripped_token)
                    runtime_store.set_setting(SETTING_TELEGRAM_CHAT_ID, stripped_chat_id)
                elif existing_token.strip():
                    # Token unchanged (password field empty) but existing token present
                    runtime_store.set_setting(SETTING_TELEGRAM_CHAT_ID, stripped_chat_id)
                else:
                    # No new token and no existing token — refuse to save chat_id alone
                    pass
        finally:
            if store is None:
                runtime_store.close()
        return RedirectResponse(
            url=f"{config.root_path}/settings", status_code=status.HTTP_303_SEE_OTHER
        )

    @app.post("/settings/test", response_class=JSONResponse)
    async def settings_test(
        request: Request,
        csrf_token: str = Form(""),
    ) -> JSONResponse:
        validate_csrf_form(request, {"csrf_token": csrf_token})
        require_authenticated_api(request)
        runtime_store = _open_store()
        try:
            env_fallback = _env_telegram_fallback(config)
            effective = resolve_telegram_config(runtime_store, env_fallback)
        finally:
            if store is None:
                runtime_store.close()
        if effective is None:
            return JSONResponse({"success": False, "detail": "Telegram is not configured."})
        from .notifications import send_telegram_message, NotificationDeliveryError
        try:
            send_telegram_message(effective, chat_id=effective.default_chat_id, text="VIGIL IDS test message from operator console.")
        except NotificationDeliveryError as exc:
            logger.warning("Settings test failed: %s", exc)
            return JSONResponse({"success": False, "detail": "Failed to send test message. Check your bot token and chat ID."})
        except ValueError as exc:
            logger.warning("Settings test config error: %s", exc)
            return JSONResponse({"success": False, "detail": "Invalid Telegram configuration."})
        return JSONResponse({"success": True, "detail": "Test message sent successfully."})

    # ── JSON API routes (unchanged from Phase 0) ─────────────────────────────

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
            if store is None:
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
            if store is None:
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
            if store is None:
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
            if store is None:
                runtime_store.close()
        return JSONResponse({"sensor_id": sensor_id, "summaries": summaries})

    return app
