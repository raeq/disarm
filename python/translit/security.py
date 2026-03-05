"""Security-oriented Unicode analysis: confusables, mixed-script detection, and hostname safety.

Usage::

    from translit.security import is_confusable, is_mixed_script, is_safe_hostname

    is_confusable("paypal.com", "pаypal.com")  # True (Cyrillic 'a')
    is_mixed_script("pаypal")                   # True
    safe, details = is_safe_hostname("example.com")
"""

from translit import (
    SafeHostnameDetails,
    detect_scripts,
    is_confusable,
    is_mixed_script,
    is_safe_hostname,
    normalize_confusables,
    security_clean,
    strip_bidi,
)
from translit._enums import Script

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
