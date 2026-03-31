import sys

from ids.console import ingest as _impl

sys.modules[__name__] = _impl
