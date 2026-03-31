import sys

from ids.console import web as _impl

sys.modules[__name__] = _impl
