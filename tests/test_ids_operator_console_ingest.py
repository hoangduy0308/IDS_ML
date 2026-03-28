from __future__ import annotations

from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ids_operator_console.db import OperatorStore  # noqa: E402
from scripts.ids_operator_console.ingest import SensorOutputIngestor  # noqa: E402


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _table_count(store: OperatorStore, table_name: str) -> int:
    row = store._connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()  # noqa: SLF001
    assert row is not None
    return int(row["count"])


def test_sensor_output_ingest_handles_append_restart_partial_and_replace(tmp_path: Path) -> None:
    alerts_path = tmp_path / "ids_live_alerts.jsonl"
    quarantine_path = tmp_path / "ids_live_quarantine.jsonl"
    summary_path = tmp_path / "ids_live_sensor_summary.jsonl"

    _append_jsonl(
        alerts_path,
        {
            "event_type": "model_prediction",
            "source_event_id": "alert-1",
            "timestamp": "2026-03-28T14:45:00+00:00",
            "severity": "high",
            "src_ip": "10.0.0.5",
            "dst_ip": "10.0.0.7",
            "src_port": 443,
            "dst_port": 51111,
            "protocol": "tcp",
            "is_alert": True,
        },
    )
    _append_jsonl(
        quarantine_path,
        {
            "event_type": "schema_anomaly",
            "source_event_id": "anom-1",
            "timestamp": "2026-03-28T14:45:01+00:00",
            "anomaly_type": "invalid_json",
            "reason": "invalid_json",
        },
    )
    _append_jsonl(
        summary_path,
        {
            "event_type": "live_sensor_summary",
            "timestamp": "2026-03-28T14:45:02+00:00",
            "alert_records": 1,
            "quarantine_records": 1,
        },
    )

    store = OperatorStore.open(tmp_path / "operator_console.db")
    try:
        ingestor = SensorOutputIngestor(
            store=store,
            alerts_input_path=alerts_path,
            quarantine_input_path=quarantine_path,
            summary_input_path=summary_path,
        )

        first_run = ingestor.run_once()
        assert first_run.alerts_ingested == 1
        assert first_run.anomalies_ingested == 1
        assert first_run.summaries_ingested == 1
        assert first_run.parse_errors == 0
        assert _table_count(store, "alerts") == 1
        assert _table_count(store, "anomalies") == 1
        assert _table_count(store, "summaries") == 1

        second_run = ingestor.run_once()
        assert second_run.alerts_ingested == 0
        assert second_run.anomalies_ingested == 0
        assert second_run.summaries_ingested == 0
        assert _table_count(store, "alerts") == 1

        with alerts_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    {
                        "event_type": "model_prediction",
                        "source_event_id": "alert-2",
                        "timestamp": "2026-03-28T14:46:00+00:00",
                        "severity": "medium",
                        "is_alert": True,
                    },
                    ensure_ascii=False,
                )
            )
            handle.write("\n")
            handle.write('{"event_type":"model_prediction","source_event_id":"alert-3"')

        partial_run = ingestor.run_once()
        assert partial_run.alerts_ingested == 1
        assert _table_count(store, "alerts") == 2
        alerts_offset_after_partial = store.get_ingest_offset("alerts")
        assert alerts_offset_after_partial is not None
        assert int(alerts_offset_after_partial["offset_bytes"]) < alerts_path.stat().st_size

        with alerts_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(',"timestamp":"2026-03-28T14:46:05+00:00","is_alert":true}')
            handle.write("\n")

        completion_run = ingestor.run_once()
        assert completion_run.alerts_ingested == 1
        assert _table_count(store, "alerts") == 3

        restarted_ingestor = SensorOutputIngestor(
            store=store,
            alerts_input_path=alerts_path,
            quarantine_input_path=quarantine_path,
            summary_input_path=summary_path,
        )
        restart_run = restarted_ingestor.run_once()
        assert restart_run.alerts_ingested == 0
        assert restart_run.anomalies_ingested == 0
        assert restart_run.summaries_ingested == 0
        assert _table_count(store, "alerts") == 3

        alerts_path.write_text(
            json.dumps(
                {
                    "event_type": "model_prediction",
                    "source_event_id": "alert-replaced",
                    "timestamp": "2026-03-28T14:47:00+00:00",
                    "severity": "low",
                    "is_alert": True,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        replace_run = restarted_ingestor.run_once()
        assert replace_run.alerts_ingested == 1
        assert _table_count(store, "alerts") == 4
    finally:
        store.close()

