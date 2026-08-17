# Upgrading disarm

This page tracks **breaking renames within disarm** — moving an existing install to a
newer disarm version. It is distinct from [Migration](migration/index.md), which covers
switching *to* disarm from a different library (unidecode, python-slugify,
confusable_homoglyphs, pathvalidate, anyascii).

Renames are cumulative below. The **semantic delta** column is the load-bearing one: a
rename that only changes the spelling is a mechanical fix, but a rename that also changes
*meaning* — like the hostname polarity inversion below — will compile and run while doing
the opposite of what you intend.

## The one that fails silently: `is_safe_hostname` → `is_suspicious_hostname`

!!! danger "The boolean was inverted — invert your branch, not just the name"
    In **0.9.1**, `is_safe_hostname` became `is_suspicious_hostname` with **no alias**, and
    the return value's meaning was **flipped** (the result field `safe` → `suspicious`, and
    the type `SafeHostnameDetails` → `HostnameAnalysis`). Every other rename fails *loudly* —
    an `ImportError`/`AttributeError` on the dead name. This one does not: a mechanical
    rename keeps working code that now means the opposite.

    ```python
    # WRONG - mechanical rename, branch polarity silently flipped
    ok, details = is_suspicious_hostname(host)
    if ok:
        allow(host)          # now allows *suspicious* hosts

    # RIGHT - invert the branch along with the name
    suspicious, analysis = is_suspicious_hostname(host)
    if not suspicious:
        allow(host)
    ```

    For a spoof-detection library, this is exactly the failure an upgrade guide exists to
    prevent. See [`is_suspicious_hostname`](api/predicates.md#is_suspicious_hostname) for the
    current API.

## All public renames since 0.9

| Old name | Replacement | Version | Semantic delta | Alias? |
|---|---|---|---|---|
| `is_safe_hostname` | `is_suspicious_hostname` | 0.9.1 | **boolean inverted** (see above) | none |
| `SafeHostnameDetails.safe` | `HostnameAnalysis.suspicious` | 0.9.1 | **inverted** | none |
| `sanitize_user_input` | `normalize_user_input` | 0.9.1 | rename only | none |
| `web_input_sanitize` (profile) | `normalize_web_input` | 0.9.1 | rename only | none |
| `security_clean` | `canonicalize` | 0.11.0 | rename only (old name over-promised safety) | deprecated alias |
| `display_clean` | `strip_format` | 0.11.0 | rename only | deprecated alias |
| `normalize_user_input` | `canonicalize_strict` | 0.11.0 | rename only | deprecated alias |

### Two-hop path: `sanitize_user_input`

Upgrading from **0.9.0** across both the 0.9.1 and 0.11 renames, `sanitize_user_input` moved
twice: `sanitize_user_input` → `normalize_user_input` (0.9.1) → `canonicalize_strict`
(0.11.0). Only the *second* hop kept a deprecated alias, so a 0.9.0 caller lands on a dead
name at the first hop with nothing to point them onward. Go straight to `canonicalize_strict`.

## When the 0.11 aliases are removed

The `security_clean` / `display_clean` / `normalize_user_input` aliases are documented as
"removed in 1.0". **"1.0" is the commercial-support milestone defined in
[RELEASING.md](RELEASING.md), not the next release** — by that policy disarm expects to stay
below 1.0 for a long time, so the aliases are not going away imminently. They will be removed
when 1.0 is cut; migrate at your convenience before then.
