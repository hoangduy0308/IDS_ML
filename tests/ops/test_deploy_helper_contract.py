from __future__ import annotations

import re
import subprocess
import tarfile
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_install_helper_keeps_in_place_editable_checkout_contract() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert "--install-root" not in install_script
    assert "--source-root" not in install_script
    assert "copy_repo_tree" not in install_script
    assert 'INSTALL_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)' in install_script
    assert 'if [[ "${INSTALL_ROOT}" != "/opt/ids_ml_new" ]]' in install_script
    assert '"${PYTHON_BIN}" -m venv --clear "${INSTALL_ROOT}/.venv"' in install_script
    assert '"${INSTALL_ROOT}/.venv/bin/python" -m pip install --no-deps -e "${INSTALL_ROOT}"' in install_script
    assert 'Cannot run --bootstrap without --candidate-bundle-root.' in install_script
    assert '--extractor-command-prefix-token P' in install_script
    assert '--extractor-command-prefix "${EXTRACTOR_COMMAND_PREFIX[@]}"' in install_script


def test_install_helper_hardens_preseeded_env_file() -> None:
    """The installer must re-permission an existing operator env file.

    The documented install path allows operators to cp the env example
    before running the installer.  If the file already exists, the
    installer must harden ownership and permissions to prevent leaking
    secrets (e.g. Telegram bot token) to other local users.
    """
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    # The else branch of seed_operator_env must apply secure permissions
    assert 'chmod 0640 "${OPERATOR_ENV_DEST}"' in install_script, (
        "install.sh must chmod existing env file to 0640"
    )
    assert 'chown root:ids-operator "${OPERATOR_ENV_DEST}"' in install_script, (
        "install.sh must chown existing env file to root:ids-operator"
    )


def test_install_helper_enables_notify_worker_service() -> None:
    """The installer must enable the notification worker alongside the base services.

    A fresh install should leave ids-operator-console-notify.service enabled
    so that Telegram notification dispatch is operational after reboot without
    requiring a separate manual post-install step.
    """
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert "ids-operator-console-notify.service" in install_script, (
        "install.sh must reference the notify worker service"
    )
    # The enable line must include all three services
    assert (
        "systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service"
        in install_script
    ), (
        "install.sh must enable ids-operator-console-notify.service alongside the base services"
    )


def test_build_release_uses_git_archive_not_manual_excludes() -> None:
    """The release helper must use git archive for a safe export surface."""
    build_script = (REPO_ROOT / "ops" / "build_release.sh").read_text(encoding="utf-8")

    # Must use git archive as the primary export mechanism
    assert "git archive" in build_script, (
        "build_release.sh must use 'git archive' to export only tracked files"
    )
    assert 'git -C "${REPO_ROOT}" archive HEAD' in build_script

    # Must NOT fall back to the old manual-exclude tar approach
    assert "tar -cf - ." not in build_script, (
        "build_release.sh must not tar the raw working tree"
    )
    assert "-cf - ." not in build_script, (
        "build_release.sh must not archive the raw working directory"
    )

    # Wheelhouse dependency building should still be present
    assert '"${PYTHON_BIN}" -m pip wheel -r "${REPO_ROOT}/requirements.txt" --wheel-dir "${WHEELHOUSE_DIR}"' in build_script

    # Must not build the project itself as a wheel (only deps)
    assert 'pip wheel "${REPO_ROOT}"' not in build_script


# ── Phase 4 closure proof: cross-surface contract verification ─────────────


def test_settings_template_is_root_path_aware() -> None:
    """The settings template must generate URLs relative to root_path.

    This is a compile-time proof that the settings form, test button,
    and any redirect-related markup honor the mounted-path contract.
    """
    template_text = (
        REPO_ROOT / "ids" / "console" / "templates" / "settings.html"
    ).read_text(encoding="utf-8")

    # Form action must be dynamically generated with root_path prefix
    assert "{{ root_path }}/settings" in template_text, (
        "settings.html form action must use {{ root_path }} prefix"
    )
    # Test button URL must be dynamically generated with root_path prefix
    assert "{{ root_path }}/settings/test" in template_text, (
        "settings.html test URL must use {{ root_path }} prefix"
    )
    # Must NOT have hardcoded action="/settings" (without root_path)
    assert 'action="/settings"' not in template_text, (
        "settings.html must not have hardcoded action='/settings'"
    )


def test_settings_js_reads_test_url_from_data_attribute() -> None:
    """The console JS must read the test URL from a data attribute,
    not hardcode it, so it works under mounted reverse-proxy paths."""
    js_text = (
        REPO_ROOT / "ids" / "console" / "static" / "console.js"
    ).read_text(encoding="utf-8")

    assert "data-test-url" in js_text, (
        "console.js must read the test URL from a data-test-url attribute"
    )
    # Must NOT have a hardcoded fetch to '/settings/test'
    assert "fetch('/settings/test'" not in js_text, (
        "console.js must not hardcode fetch('/settings/test')"
    )


def test_effective_telegram_config_resolver_shared_across_surfaces() -> None:
    """The web layer, runtime, and preflight must all use the same
    resolve_telegram_config function for the DB > env fallback rule."""
    web_text = (REPO_ROOT / "ids" / "console" / "web.py").read_text(encoding="utf-8")
    runtime_text = (REPO_ROOT / "ids" / "console" / "notification_runtime.py").read_text(encoding="utf-8")
    preflight_text = (REPO_ROOT / "ids" / "ops" / "operator_console_preflight.py").read_text(encoding="utf-8")

    # web.py must import and use resolve_telegram_config
    assert "from .notification_runtime import resolve_telegram_config" in web_text, (
        "web.py must import resolve_telegram_config from notification_runtime"
    )
    assert "resolve_telegram_config(" in web_text, (
        "web.py must call resolve_telegram_config"
    )

    # notification_runtime.py must define and export resolve_telegram_config
    assert "def resolve_telegram_config(" in runtime_text, (
        "notification_runtime.py must define resolve_telegram_config"
    )
    assert '"resolve_telegram_config"' in runtime_text, (
        "notification_runtime.py must export resolve_telegram_config in __all__"
    )

    # preflight must check DB settings (same precedence rule)
    assert "_load_telegram_settings_from_db" in preflight_text, (
        "preflight must load Telegram settings from DB"
    )


def test_env_example_documents_full_telegram_surface() -> None:
    """The env example must document the complete Telegram configuration surface
    including env vars, token file, chat ID, and the Settings UI alternative."""
    env_text = (REPO_ROOT / "ops" / "ids-operator-console.env.example").read_text(encoding="utf-8")

    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN=" in env_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE=" in env_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID=" in env_text
    assert "Settings UI" in env_text, (
        "Env example must mention the Settings UI as an alternative config path"
    )
    assert "DB settings" in env_text or "database" in env_text.lower(), (
        "Env example must explain DB precedence"
    )


def test_deployment_docs_match_corrected_install_contract() -> None:
    """The deployment quickstart docs must match the repaired install/runtime behavior."""
    docs_text = (
        REPO_ROOT / "docs" / "current" / "operations" / "deployment_quickstart.md"
    ).read_text(encoding="utf-8")

    # Must document git archive as the safe export surface
    assert "git archive" in docs_text or "git-tracked export" in docs_text, (
        "Docs must describe the safe export surface (git archive)"
    )
    # Must document the Settings UI approach
    assert "Settings" in docs_text, (
        "Docs must mention the Settings UI for Telegram configuration"
    )
    # Must document the env file approach
    assert "Environment file" in docs_text or "environment file" in docs_text or "env file" in docs_text, (
        "Docs must mention the environment file approach"
    )
    # Must document DB precedence
    assert "precedence" in docs_text.lower() or "take priority" in docs_text.lower() or "wins" in docs_text.lower(), (
        "Docs must explain DB settings precedence over env"
    )
    # Must document the notify worker
    assert "ids-operator-console-notify" in docs_text, (
        "Docs must mention the notification worker service"
    )


def test_git_archive_excludes_ignored_and_untracked_files() -> None:
    """Regression: prove that git archive does not include ignored/untracked files.

    This test creates a temporary untracked file in the repo, runs git archive,
    and verifies the file is absent from the produced tarball.  This is the
    concrete proof that the safe export surface works.
    """
    # Pick a filename that is clearly not tracked and is .gitignore'd
    # (.claude is listed in .gitignore)
    sentinel_name = ".claude/_test_leak_sentinel.txt"
    sentinel_path = REPO_ROOT / sentinel_name

    # Also test a random untracked file outside .gitignore
    untracked_name = "_untracked_secret_test_file.tmp"
    untracked_path = REPO_ROOT / untracked_name

    try:
        # Create sentinel files
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        sentinel_path.write_text("THIS MUST NOT APPEAR IN RELEASE", encoding="utf-8")
        untracked_path.write_text("THIS MUST NOT APPEAR IN RELEASE", encoding="utf-8")

        # Run git archive and capture the tarball
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "archive", "HEAD", "-o", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"git archive failed: {result.stderr}"

        # Inspect the tarball contents
        with tarfile.open(tmp_path, "r") as tf:
            archive_names = tf.getnames()

        # The sentinel files MUST be absent
        assert sentinel_name not in archive_names, (
            f"Ignored file {sentinel_name!r} was included in git archive output"
        )
        assert untracked_name not in archive_names, (
            f"Untracked file {untracked_name!r} was included in git archive output"
        )

        # Sanity: some known tracked files SHOULD be present
        assert any("pyproject.toml" in n for n in archive_names), (
            "pyproject.toml should be in the archive"
        )
        assert any("ids/__init__.py" in n for n in archive_names), (
            "ids/__init__.py should be in the archive"
        )

    finally:
        # Clean up sentinel files
        if sentinel_path.exists():
            sentinel_path.unlink()
        if untracked_path.exists():
            untracked_path.unlink()
        if tmp_path.exists():
            tmp_path.unlink()
        # Clean up .claude dir if we created it and it's empty
        if sentinel_path.parent.exists():
            try:
                sentinel_path.parent.rmdir()
            except OSError:
                pass  # Not empty (other files exist), leave it


# ── Phase 4 closure proof tests ────────────────────────────────────────────


def test_deploy_surface_closure_proof() -> None:
    """Comprehensive proof that the Phase 4 deploy surface repairs hold together.

    This test verifies all three fix domains in a single pass:
    1. Release artifact safety (git archive, no raw-tree tar)
    2. Install-time hardening (env file perms, notify service enable)
    3. Docs alignment (quickstart and README reflect corrected behavior)
    """
    build_script = (REPO_ROOT / "ops" / "build_release.sh").read_text(encoding="utf-8")
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    # ── 1. Release artifact safety ──────────────────────────────────────
    # git archive is the export mechanism, not raw-tree tar
    assert "git archive" in build_script
    assert "-cf - ." not in build_script

    # ── 2. Install-time hardening ─────────────────────────────────────��─
    # Pre-seeded env file gets hardened
    assert 'chmod 0640 "${OPERATOR_ENV_DEST}"' in install_script
    assert 'chown root:ids-operator "${OPERATOR_ENV_DEST}"' in install_script
    # Notify worker is enabled with the base services
    assert re.search(
        r"systemctl enable.*ids-operator-console-notify\.service",
        install_script,
    ), "install.sh must enable the notify worker service"

    # ── 3. Docs alignment ───────────────────────────────────────────────
    quickstart = (REPO_ROOT / "docs" / "current" / "operations" / "deployment_quickstart.md")
    if quickstart.exists():
        qs_text = quickstart.read_text(encoding="utf-8")
        # Must mention git archive or tracked-only export
        assert "git archive" in qs_text or "tracked" in qs_text.lower(), (
            "deployment_quickstart.md must document the safe export surface"
        )
        # Must document effective Telegram config behavior
        assert "fallback" in qs_text.lower() or "precedence" in qs_text.lower(), (
            "deployment_quickstart.md must document Telegram config precedence"
        )

    ops_readme = REPO_ROOT / "ops" / "README-deploy.md"
    if ops_readme.exists():
        ops_text = ops_readme.read_text(encoding="utf-8")
        # Must document the notify worker
        assert "ids-operator-console-notify" in ops_text, (
            "README-deploy.md must reference the notification worker service"
        )
        # Must document config precedence
        assert "precedence" in ops_text.lower() or "database" in ops_text.lower(), (
            "README-deploy.md must document DB > env config precedence"
        )


def test_settings_effective_config_contract_aligns_web_and_runtime() -> None:
    """Prove that web.py and notification_runtime.py use the same resolver.

    This is a static proof that the settings page and the runtime worker
    use the same resolve_telegram_config function, not separate
    reimplementations.
    """
    web_source = (REPO_ROOT / "ids" / "console" / "web.py").read_text(encoding="utf-8")

    # web.py must import resolve_telegram_config from notification_runtime
    assert "from .notification_runtime import resolve_telegram_config" in web_source, (
        "web.py must import resolve_telegram_config from notification_runtime"
    )
    # web.py settings_page must use resolve_telegram_config_with_source
    assert "resolve_telegram_config_with_source(" in web_source, (
        "settings_page must call resolve_telegram_config_with_source"
    )
    # web.py settings_test must use resolve_telegram_config
    assert "resolve_telegram_config(runtime_store, env_fallback)" in web_source, (
        "settings_test must call resolve_telegram_config with env fallback"
    )


def test_install_helper_hardens_db_file_permissions() -> None:
    """The installer must harden the SQLite DB file that now stores the bot token.

    After bootstrap or on a subsequent install run, the DB file should be
    chmod 0640 and chown root:ids-operator to prevent other local users
    from reading the plaintext Telegram bot token.
    """
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert "chmod 0640 /var/lib/ids-operator-console/operator_console.db" in install_script, (
        "install.sh must chmod the DB file to 0640"
    )
    assert "chown root:ids-operator /var/lib/ids-operator-console/operator_console.db" in install_script, (
        "install.sh must chown the DB file to root:ids-operator"
    )


def test_settings_root_path_contract() -> None:
    """Prove that the settings template is root-path-aware.

    This is a static proof that the form action and test URL
    use root_path from the template context.
    """
    template_path = REPO_ROOT / "ids" / "console" / "templates" / "settings.html"
    template_source = template_path.read_text(encoding="utf-8")

    # Form action must be root-path-aware
    assert "{{ root_path }}/settings" in template_source, (
        "settings.html form action must use root_path"
    )
    # Test URL must be root-path-aware
    assert "{{ root_path }}/settings/test" in template_source, (
        "settings.html test URL must use root_path"
    )
