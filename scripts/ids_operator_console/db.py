import sys

from ids.console import db as _impl

sys.modules[__name__] = _impl
