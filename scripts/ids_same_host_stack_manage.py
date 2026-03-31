from pathlib import Path
import sys

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from ids.ops.same_host_stack_manage import *  # noqa: F401,F403


if __name__ == "__main__":
    raise SystemExit(main())
