"""The Python side of rust_oracle/src/bin/core_repro.rs (README: E1, E2)."""

import disarm

disarm.register_replacements({"foo": "bar"})
print('after register_replacements({"foo": "bar"}):')
print("  transliterate('foo')             =", ascii(disarm.transliterate("foo")))
print("  transliterate('foo', lang='de')  =", ascii(disarm.transliterate("foo", lang="de")))
print("  slugify('foo')                   =", ascii(disarm.slugify("foo")))
print("  search_key('foo')                =", ascii(disarm.search_key("foo")))
disarm.seal_registrations()
try:
    disarm.register_replacements({})
except disarm.DisarmError as e:
    print(
        "  register_replacements after seal raised",
        type(e).__name__,
        "| UnsupportedError?",
        isinstance(e, disarm.UnsupportedError),
    )
