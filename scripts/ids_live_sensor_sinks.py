from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from ids.runtime import live_sensor_sinks as _impl


if __name__ != "__main__":
    sys.modules[__name__] = _impl
