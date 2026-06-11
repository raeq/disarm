"""DEPRECATED: ``translit-rs`` has been renamed to ``disarm``.

Install and import ``disarm`` instead::

    pip install disarm
    import disarm

This 0.8.2 release is a thin compatibility shim: it depends on ``disarm`` and
re-exports its public API so existing ``import translit`` code keeps working
(with a :class:`DeprecationWarning`). The last functional release under the old
name was ``translit-rs 0.8.1``.

Rename notes (see https://github.com/raeq/disarm/issues/264):
  * ``TranslitError`` -> ``DisarmError`` (aliased below for back-compat).
  * the env var ``TRANSLIT_DICT_DIR`` -> ``DISARM_DICT_DIR``.
The transform API (``transliterate``, ``normalize``, ``slugify``, ...) is
unchanged.
"""

from __future__ import annotations

import warnings as _warnings

_warnings.warn(
    "translit-rs has been renamed to 'disarm' and is no longer maintained under "
    "the old name. Install 'disarm' (pip install disarm) and use 'import disarm'. "
    "This translit-rs 0.8.2 shim re-exports disarm and will not receive updates.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export the full public API of disarm so `import translit` keeps working.
from disarm import *  # noqa: E402, F401, F403

# Back-compat alias for the renamed base exception (TranslitError -> DisarmError).
from disarm import DisarmError as TranslitError  # noqa: E402
from disarm import __all__ as _disarm_all  # noqa: E402

__all__ = [*_disarm_all, "TranslitError"]

# `translit.__version__` reports the translit-rs *distribution* version (0.8.2),
# not disarm's — a consumer pinning on `translit.__version__` is asking about the
# translit-rs package, which is frozen at this final 0.8.2 shim release.
__version__ = "0.8.2"
