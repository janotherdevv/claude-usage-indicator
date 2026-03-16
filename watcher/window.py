# Compatibility shim — do not add imports here.
# Import from watcher.windows directly for anything other than UsageWindow.
from .windows import UsageWindow  # noqa: F401
