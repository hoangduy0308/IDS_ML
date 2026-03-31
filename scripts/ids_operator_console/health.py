import sys

from ids.console import health as _impl

sys.modules[__name__] = _impl
