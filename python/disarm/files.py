"""Filename sanitization utilities.

Usage::

    from disarm.files import sanitize_filename

    safe_name = sanitize_filename("CON.txt", platform="windows")
"""

from disarm import sanitize_filename

__all__ = [
    "sanitize_filename",
]
