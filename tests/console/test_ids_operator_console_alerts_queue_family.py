"""Queue-level family fallback smoke tests for the alerts table."""

from __future__ import annotations

from pathlib import Path
import re

from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.console.auth import ensure_admin_user  # noqa: E402
from ids.console.config import load_operator_console_config  # noqa: E402
from ids.console.db import open_existing_operator_store  # noqa: E402
from ids.console.migrations import migrate_operator_store  # noqa: E402
from ids.console.web import create_operator_console_web_app  # noqa: E402


def _build_queue_family_test_app(tmp_path: Path) -> TestClient:
    env = {
        "IDS_OPERATOR_CONSOLE_ENVIRONMENT": "development",
        "IDS_OPERATOR_CONSOLE_SECRET_KEY": "queue-family-test-secret",
        "IDS_OPERATOR_CONSOLE_DATABASE_PATH": str(tmp_path / "operator_console_queue_family.db"),
        "IDS_OPERATOR_CONSOLE_TEMPLATES_DIR": str(REPO_ROOT / "ids/console/templates"),
        "IDS_OPERATOR_CONSOLE_STATIC_DIR": str(REPO_ROOT / "ids/console/static"),
    }
    config = load_operator_console_config(environ=env, repo_root=REPO_ROOT)
    migrate_operator_store(config.database_path, allow_bootstrap=True)
    store = open_existing_operator_store(config.database_path)
    try:
        ensure_admin_user(store, username="admin", password="secret")
        store.upsert_alert(
            source_event_id="queue-family-known",
            event_ts="2026-03-30T10:00:00+00:00",
            severity="high",
            src_ip="10.20.0.3",
            dst_ip="192.168.1.30",
            src_port=3333,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-queue-known",
            payload={
                "family_status": "known",
                "attack_family": "mirai",
                "attack_family_confidence": 0.97,
                "attack_family_margin": 0.42,
            },
        )
        store.upsert_alert(
            source_event_id="queue-family-unknown",
            event_ts="2026-03-30T11:00:00+00:00",
            severity="high",
            src_ip="10.20.0.4",
            dst_ip="192.168.1.31",
            src_port=4444,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-queue-unknown",
            payload={
                "family_status": "unknown",
                "attack_family_confidence": 0.49,
                "attack_family_margin": 0.01,
            },
        )
        store.upsert_alert(
            source_event_id="queue-family-benign",
            event_ts="2026-03-30T11:30:00+00:00",
            severity="medium",
            src_ip="10.20.0.6",
            dst_ip="192.168.1.33",
            src_port=6666,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-queue-benign",
            payload={
                "family_status": "benign",
                "attack_family": "mirai",
                "attack_family_confidence": 0.33,
                "attack_family_margin": 0.77,
            },
        )
        store.upsert_alert(
            source_event_id="queue-family-legacy",
            event_ts="2026-03-30T12:00:00+00:00",
            severity="medium",
            src_ip="10.20.0.5",
            dst_ip="192.168.1.32",
            src_port=5555,
            dst_port=443,
            protocol="tcp",
            fingerprint="fp-queue-legacy",
            payload={"score": 0.82},
        )
    finally:
        store.close()

    app = create_operator_console_web_app(config)
    return TestClient(app, base_url="http://testserver")


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Login failed: {response.status_code}"


def _family_cell_html(body: str, source_event_id: str) -> str:
    marker = f">{source_event_id}</a>"
    marker_index = body.find(marker)
    assert marker_index != -1, f"Could not find row for {source_event_id}"
    row_start = body.rfind("<tr", 0, marker_index)
    row_end = body.find("</tr>", marker_index)
    assert row_start != -1 and row_end != -1, f"Could not isolate row for {source_event_id}"
    row_html = body[row_start : row_end + len("</tr>")]
    cell_match = re.search(
        r'<td style="min-width:180px;vertical-align:top">(.*?)</td>',
        row_html,
        re.DOTALL,
    )
    assert cell_match, f"Could not find family cell for {source_event_id}"
    return cell_match.group(1)


def test_alerts_queue_family_fallback_copy_is_honest(tmp_path: Path) -> None:
    client = _build_queue_family_test_app(tmp_path)
    _login(client)

    response = client.get("/alerts")
    assert response.status_code == 200
    body = response.text.lower()

    assert "known family" in body
    assert "mirai" in body
    assert "unknown family" in body
    assert "attack, no confident family assigned" in body
    assert "family unavailable" in body
    assert "legacy alert from before family enrichment" in body


def test_alerts_queue_benign_rows_stay_family_neutral(tmp_path: Path) -> None:
    client = _build_queue_family_test_app(tmp_path)
    _login(client)

    response = client.get("/alerts")
    assert response.status_code == 200

    family_cell = _family_cell_html(response.text, "queue-family-benign")
    assert "badge" not in family_cell.lower()
    assert "benign" not in family_cell.lower()
    assert "—" in family_cell
