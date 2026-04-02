from pathlib import Path

from repo_installable_proof_support import shared_editable_repo_python

SHARED_EDITABLE_INSTALL_CACHE_KEY = "repo-installable-proof"


def shared_editable_install_python() -> Path:
    return shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)
