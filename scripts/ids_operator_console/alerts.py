import sys

from ids.console import alerts as _impl

sys.modules[__name__] = _impl
