from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from ids.runtime import live_flow_bridge as _impl

globals().update({name: value for name, value in _impl.__dict__.items() if not name.startswith("__")})
sys.modules[__name__] = _impl
