import sys

from ids.console import notifications as _impl

sys.modules[__name__] = _impl
