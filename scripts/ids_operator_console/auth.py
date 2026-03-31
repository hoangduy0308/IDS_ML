import sys

from ids.console import auth as _impl

sys.modules[__name__] = _impl
