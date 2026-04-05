from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _install_script_text() -> str:
    return (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")


def test_install_help_exposes_explicit_mode_selection() -> None:
    install_script = _install_script_text()

    assert "--mode MODE" in install_script
    assert "Install mode: console-only or full-stack-same-host" in install_script
    assert "console-only runs console schema migration + admin bootstrap through ids-operator-console-manage" in install_script
    assert "full-stack-same-host auto-runs ids-stack bootstrap with the bundled default artifact" in install_script


def test_install_mode_validation_distinguishes_console_only_from_full_stack() -> None:
    install_script = _install_script_text()

    require_mode_def = install_script.index("require_mode() {")
    ensure_mode_def = install_script.index("ensure_mode_contract() {")
    call_site = install_script.index("require_mode\nensure_mode_contract")

    assert "require_mode" in install_script
    assert "ensure_mode_contract" in install_script
    assert 'console-only mode does not accept bootstrap or bundle inputs.' in install_script
    assert 'console-only mode requires --create-secrets or --admin-password-file.' in install_script
    assert 'full-stack-same-host mode requires --bootstrap.' in install_script
    assert 'Missing required --mode. Use console-only or full-stack-same-host.' in install_script
    assert require_mode_def < call_site
    assert ensure_mode_def < call_site


def test_install_mode_services_are_routed_by_product_shape() -> None:
    install_script = _install_script_text()

    assert 'systemctl enable ids-operator-console.service ids-operator-console-notify.service' in install_script
    assert 'systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service' in install_script
    assert '[6/6] Enabling console-only services...' in install_script
    assert '[6/6] Enabling full-stack services...' in install_script
    assert 'Finalizing %s install path...' in install_script


def test_install_mode_service_routing_keeps_console_only_bundle_free() -> None:
    install_script = _install_script_text()
    enable_start = install_script.index("enable_mode_services() {")
    install_python_start = install_script.index("install_python_product()")
    enable_block = install_script[enable_start:install_python_start]

    assert 'if [[ "${MODE}" == "console-only" ]]; then' in enable_block
    assert 'systemctl enable ids-operator-console.service ids-operator-console-notify.service >/dev/null' in enable_block
    assert 'systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service >/dev/null' in enable_block
    assert 'return' in enable_block

    console_only_block = enable_block.split('if [[ "${MODE}" == "console-only" ]]; then', 1)[1].split('return', 1)[0]
    full_stack_block = enable_block.split('return', 1)[1]

    assert 'ids-live-sensor.service' not in console_only_block
    assert 'ids-operator-console-notify.service' in console_only_block
    assert 'ids-live-sensor.service' in full_stack_block


def test_install_mode_next_checks_document_mode_specific_readiness() -> None:
    install_script = _install_script_text()

    assert "Next checks:" in install_script
    assert "if [[ \"${MODE}\" == \"console-only\" ]]; then" in install_script
    assert "console-only" in install_script
    assert "--json status" in install_script
    assert "--json status" in install_script
    assert "--json smoke" in install_script
    assert "--json notify-status" in install_script
    assert 'SENSOR_STATE_DIR="/var/lib/ids-live-sensor"' in install_script
    assert 'SENSOR_STATE_DIR="${IDS_INSTALL_SENSOR_STATE_DIR:-${SENSOR_STATE_DIR}}"' in install_script
    assert "ids-model-bundle-manage --activation-path ${SENSOR_STATE_DIR}/active_bundle.json --json status" in install_script
    next_checks_start = install_script.index("printf 'Next checks:\\n'")
    console_branch_start = install_script.index('if [[ "${MODE}" == "console-only" ]]; then', next_checks_start)
    console_branch_end = install_script.index('else', console_branch_start)
    console_only_block = install_script[console_branch_start:console_branch_end]
    assert "ids-stack --repo-root" not in console_only_block
    assert "full-stack-same-host" in install_script
    assert "console-only" in install_script
