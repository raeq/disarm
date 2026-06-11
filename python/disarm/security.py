"""Security-oriented Unicode analysis: confusables, mixed-script detection, and hostname safety.

Usage::

    from disarm.security import is_confusable, is_mixed_script, is_safe_hostname

    is_confusable("pаypal")                     # True (contains Cyrillic 'а')
    is_mixed_script("pаypal")                   # True
    safe, details = is_safe_hostname("example.com")
"""

from disarm import (
    SafeHostnameDetails,
    detect_scripts,
    is_confusable,
    is_mixed_script,
    is_safe_hostname,
    normalize_confusables,
    security_clean,
    strip_bidi,
)
from disarm._enums import Script

__all__ = [
    "SafeHostnameDetails",
    "Script",
    "detect_scripts",
    "is_confusable",
    "is_mixed_script",
    "is_safe_hostname",
    "normalize_confusables",
    "security_clean",
    "strip_bidi",
]
