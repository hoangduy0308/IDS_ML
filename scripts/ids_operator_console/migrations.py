import sys

from ids.console import migrations as _impl

sys.modules[__name__] = _impl
