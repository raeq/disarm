- **`python/disarm/_api.py` is split by concern.** The 3,958-line module keeps the four
  functions declared with `@overload` stubs (`transliterate`'s dispatcher, `slugify`,
  `normalize` and `strip_accents`), because `typing.get_overloads` finds overloads by
  the module that declared them, and the stateful surface (`Slugifier`,
  `UniqueSlugifier`, `TextPipeline`, the registration functions and the caches that
  watch them). The stateless function families move into private modules beside it:
  `_api_text.py`, `_api_confusables.py`, `_api_translit.py`, `_api_scripts.py`,
  `_api_security.py`, `_api_encoding.py`, `_api_emoji.py`, `_api_graphemes.py` and
  `_api_common.py`. Every function moved verbatim. `disarm._api` re-exports each one
  under its old name and still reports itself as their module, so
  `from disarm._api import ...`, `help()`, pickling, `typing.get_overloads` and the
  package root are unchanged. The one test that patched a name there, `_detect_scripts`,
  patches it in `disarm._api_scripts`, the module that now reads it.
