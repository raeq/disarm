"""Security-oriented Unicode analysis: confusables, mixed-script detection, and hostname safety.

Usage::

    from disarm.security import is_confusable, is_mixed_script, is_suspicious_hostname

    is_confusable("pаypal")                     # True (contains Cyrillic 'а')
    find_key_collisions(["admin", "аdmin"], key="search_key")   # one group
    is_mixed_script("pаypal")                   # True
    suspicious, analysis = is_suspicious_hostname("example.com")
"""

from disarm import (
    HostnameAnalysis,
    KeyCollision,
    canonicalize,
    detect_scripts,
    find_key_collisions,
    is_confusable,
    is_mixed_script,
    is_suspicious_hostname,
    normalize_confusables,
    security_clean,
    strip_bidi,
)
from disarm._enums import Script

__all__ = [
    "HostnameAnalysis",
    "KeyCollision",
    "Script",
    "canonicalize",
    "detect_scripts",
    "find_key_collisions",
    "is_confusable",
    "is_mixed_script",
    "is_suspicious_hostname",
    "normalize_confusables",
    "security_clean",  # deprecated alias for canonicalize (#430), removed in 1.0
    "strip_bidi",
]
