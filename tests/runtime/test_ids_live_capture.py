from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

from ids.runtime.live_capture import (  # noqa: E402
    CaptureBacklogExceededError,
    DumpcapCaptureConfig,
    RollingDumpcapCaptureManager,
)


def make_manager(
    tmp_path: Path,
    *,
    interface: str = "eth0",
    window_duration_seconds: float = 2.5,
    window_file_count: int = 2,
    max_pending_windows: int = 2,
    capture_buffer_megabytes: int = 64,
    update_interval_seconds: float = 0.5,
) -> RollingDumpcapCaptureManager:
    config = DumpcapCaptureConfig(
        interface=interface,
        spool_dir=tmp_path / "spool",
        window_duration_seconds=window_duration_seconds,
        window_file_count=window_file_count,
        max_pending_windows=max_pending_windows,
        capture_buffer_megabytes=capture_buffer_megabytes,
        update_interval_seconds=update_interval_seconds,
    )
    return RollingDumpcapCaptureManager(config, time_source=lambda: 100.0)


def test_config_rejects_blank_interface_and_non_pcap_output(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="interface"):
        DumpcapCaptureConfig(
            interface=" ",
            spool_dir=tmp_path / "spool",
            window_duration_seconds=1.0,
            window_file_count=2,
            max_pending_windows=2,
        )

    with pytest.raises(ValueError, match="pcap"):
        DumpcapCaptureConfig(
            interface="eth0",
            spool_dir=tmp_path / "spool",
            window_duration_seconds=1.0,
            window_file_count=2,
            max_pending_windows=2,
            output_format="pcapng",
        )


def test_build_dumpcap_command_enforces_tcp_udp_filter_and_pcap_output(tmp_path: Path) -> None:
    manager = make_manager(
        tmp_path,
        window_duration_seconds=12.5,
        window_file_count=4,
        max_pending_windows=4,
        capture_buffer_megabytes=32,
        update_interval_seconds=0.25,
    )

    command = manager.build_dumpcap_command()
    prefix = Path(command[command.index("-w") + 1])
    b_values = [command[index + 1] for index, token in enumerate(command) if token == "-b"]

    assert command[:2] == ["dumpcap", "-i"]
    assert command[2] == "eth0"
    assert command[command.index("-f") + 1] == "tcp or udp"
    assert command[command.index("-F") + 1] == "pcap"
    assert command[command.index("-B") + 1] == "32"
    assert command[command.index("--update-interval") + 1] == "0.25"
    assert b_values == ["duration:12.5", "files:4", f"printname:{prefix}"]
    assert prefix.parent == tmp_path / "spool"
    assert prefix.name == "eth0-window"

    with pytest.raises(ValueError, match="tcp or udp"):
        DumpcapCaptureConfig(
            interface="eth0",
            spool_dir=tmp_path / "spool",
            window_duration_seconds=1.0,
            window_file_count=2,
            max_pending_windows=2,
            capture_filter="icmp",
        )


def test_parse_closed_window_notification_extracts_path_and_ignores_noise(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)

    assert manager.parse_closed_window_notification("dumpcap: listening on eth0") is None

    window_path = tmp_path / "spool" / "eth0-window-00001.pcap"
    line = f"dumpcap: file closed {window_path}"
    event = manager.parse_closed_window_notification(line, observed_at=12.5)

    assert event is not None
    assert event.path == window_path
    assert event.interface == "eth0"
    assert event.observed_at == 12.5
    assert event.notification == line


def test_window_rollover_wraps_file_slots_and_backlog_is_bounded(tmp_path: Path) -> None:
    manager = make_manager(tmp_path, window_file_count=2, max_pending_windows=2)

    assert manager.window_path_for_sequence(0).name == "eth0-window-00000.pcap"
    assert manager.window_path_for_sequence(1).name == "eth0-window-00001.pcap"
    assert manager.window_path_for_sequence(2).name == "eth0-window-00000.pcap"

    first = manager.record_closed_window_notification(
        f"dumpcap: file closed {manager.window_path_for_sequence(0)}",
        observed_at=96.0,
    )
    second = manager.record_closed_window_notification(
        f"dumpcap: file closed {manager.window_path_for_sequence(1)}",
        observed_at=98.0,
    )

    snapshot = manager.backlog_snapshot(now=100.0)
    assert snapshot.pending_windows == 2
    assert snapshot.pending_paths == (first.path, second.path)
    assert snapshot.oldest_pending_age_seconds == pytest.approx(4.0)

    consumed = manager.acknowledge_window_consumed(first.path)
    assert consumed == first

    snapshot = manager.backlog_snapshot(now=100.0)
    assert snapshot.pending_windows == 1
    assert snapshot.pending_paths == (second.path,)
    assert snapshot.oldest_pending_age_seconds == pytest.approx(2.0)

    overflow_manager = make_manager(tmp_path, window_file_count=2, max_pending_windows=2)
    overflow_manager.record_closed_window_notification(
        f"dumpcap: file closed {overflow_manager.window_path_for_sequence(0)}",
        observed_at=96.0,
    )
    overflow_manager.record_closed_window_notification(
        f"dumpcap: file closed {overflow_manager.window_path_for_sequence(1)}",
        observed_at=98.0,
    )
    with pytest.raises(CaptureBacklogExceededError, match="pending closed windows"):
        overflow_manager.record_closed_window_notification(
            f"dumpcap: file closed {overflow_manager.window_path_for_sequence(2)}",
            observed_at=99.0,
        )


def test_classify_capture_failures_distinguishes_fatal_and_recoverable(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)

    fatal = manager.classify_capture_failure(
        stage="startup",
        returncode=2,
        stderr="dumpcap: No such device exists",
    )
    recoverable = manager.classify_capture_failure(
        stage="runtime",
        returncode=0,
        stderr="dumpcap: capture stopped by request",
    )

    assert fatal.classification == "fatal"
    assert fatal.is_fatal is True
    assert fatal.reason == "fatal_startup_or_runtime_error"
    assert recoverable.classification == "recoverable"
    assert recoverable.is_fatal is False
    assert recoverable.reason == "expected_stop_or_rotation"
