from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _install_script_text() -> str:
    return (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")


def test_install_help_exposes_explicit_mode_selection() -> None:
    install_script = _install_script_text()

    assert "--mode MODE" in install_script
    assert "Install mode: console-only or full-stack-same-host" in install_script
    assert "console-only ends with the operator console + notification worker" in install_script
    assert "full-stack-same-host remains bootstrappable through ids-stack" in install_script


def test_install_mode_validation_distinguishes_console_only_from_full_stack() -> None:
    install_script = _install_script_text()

    assert "require_mode" in install_script
    assert "ensure_mode_contract" in install_script
    assert 'console-only mode does not accept bootstrap or bundle inputs.' in install_script
    assert 'full-stack-same-host mode requires --bootstrap.' in install_script
    assert 'Missing required --mode. Use console-only or full-stack-same-host.' in install_script


def test_install_mode_services_are_routed_by_product_shape() -> None:
    install_script = _install_script_text()

    assert 'systemctl enable --now ids-operator-console.service ids-operator-console-notify.service' in install_script
    assert 'systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service' in install_script
    assert '[6/6] Enabling and starting console-only services...' in install_script
    assert '[6/6] Enabling full-stack services...' in install_script
    assert 'Finalizing %s install path...' in install_script


def test_install_mode_next_checks_document_mode_specific_readiness() -> None:
    install_script = _install_script_text()

    assert "Next checks:" in install_script
    assert "--json bootstrap --candidate-bundle-root <bundle-root>" in install_script
    assert "--proxy-public-url https://console.example --json smoke" in install_script
    assert "console-only" in install_script
    assert "full-stack-same-host" in install_script
