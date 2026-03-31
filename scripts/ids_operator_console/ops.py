import sys

from ids.console import ops as _impl

sys.modules[__name__] = _impl
