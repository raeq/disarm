"""Finding 8: the hostname screen reports a zero-width space in a label and misses 28 other
invisible code points that UTS #46 deletes the same way."""

import disarm

for h in [
    "ev\u200bil.com",
    "ev\u00adil.com",
    "ev\u034fil.com",
    "ev\u206ail.com",
    "ev\u180bil.com",
    "ev\U0001d173il.com",
    "ev\u115fil.com",
]:
    suspicious, a = disarm.is_suspicious_hostname(h)
    print(ascii(h), suspicious, a.has_invisible, a.canonical)
