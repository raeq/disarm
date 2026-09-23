"""Finding 3: canonically equivalent inputs get different verdicts. The NFC spelling, the one
text nearly always arrives in, is the unreported one for `bidi` and `invisible`."""

import unicodedata

import disarm

for s in [
    "\u00e9t\u00e9\u2067",
    "\u00e9\u200d\u00e9",
    "\u00e0\u00e9\u200f1",
    "Fran\u00e7ais",
    "ch\u1ec9",
]:
    nfc, nfd = unicodedata.normalize("NFC", s), unicodedata.normalize("NFD", s)
    print(
        ascii(nfc),
        disarm.inspect_anomalies(nfc).kinds,
        "|",
        ascii(nfd),
        disarm.inspect_anomalies(nfd).kinds,
    )
