import sys

from ids.console import notification_runtime as _impl

sys.modules[__name__] = _impl
