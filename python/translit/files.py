"""Filename sanitization utilities.

Usage::

    from translit.files import sanitize_filename

    safe_name = sanitize_filename("CON.txt", platform="windows")
"""

from translit import sanitize_filename

__all__ = [
    "sanitize_filename",
]
