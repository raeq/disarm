"""Harness runner for the C ABI (`libdisarm_ffi.so`), driven through ctypes.

ctypes is used as an ordinary C caller: arguments are NUL-terminated UTF-8
`char *`, every returned `char *` (and both halves of every `DisarmResult`) is
copied out and then released with `disarm_string_free`, exactly as `disarm.h`
prescribes. The memory-safety side of the contract is exercised separately, from
real C, by `../cabi/` under AddressSanitizer and valgrind.

    DISARM_FFI=/path/to/libdisarm_ffi.so python3 c_runner.py crc CORPUS CASES

The C ABI cannot carry U+0000 (a C string ends there), so that one input is skipped.
Errors carry no kind across this ABI, only a message, so they are encoded with the
kind `c`; the driver compares C errors by message.
"""

from __future__ import annotations

import ctypes as C
import json
import os
import sys
from collections.abc import Callable
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from proto import Err, Rec, main  # noqa: E402

lib = C.CDLL(os.environ["DISARM_FFI"])


class DisarmResult(C.Structure):
    _fields_ = [("value", C.c_void_p), ("error", C.c_void_p)]


lib.disarm_string_free.argtypes = [C.c_void_p]
lib.disarm_string_free.restype = None

STR = "str"
RES = "res"
BOOL = "bool"
U64 = "u64"
USIZE = "usize"
I8 = "i8"

_restypes = {
    STR: C.c_void_p,
    RES: DisarmResult,
    BOOL: C.c_bool,
    U64: C.c_uint64,
    USIZE: C.c_size_t,
    I8: C.c_int8,
}


def take(p: int | None) -> str | None:
    if not p:
        return None
    try:
        return C.string_at(p).decode("utf-8")
    finally:
        lib.disarm_string_free(p)


def fn(name: str, ret: str, *argtypes: Any) -> Callable[..., Any]:
    f = getattr(lib, name)
    f.argtypes = list(argtypes)
    f.restype = _restypes[ret]

    def call(*args: Any) -> Any:
        conv = [a.encode("utf-8") if isinstance(a, str) else a for a in args]
        r = f(*conv)
        if ret == STR:
            v = take(r)
            if v is None:
                raise Err("c", "NULL return")
            return v
        if ret == RES:
            value, error = take(r.value), take(r.error)
            if (value is None) == (error is None):
                raise Err("c", f"DisarmResult invariant broken: value={value!r} error={error!r}")
            if error is not None:
                raise Err("c", error)
            return value
        return r

    return call


P = C.c_char_p
tr = fn("disarm_transliterate", STR, P)
tr_opts = fn("disarm_transliterate_opts", RES, P, P, P)
rv = fn("disarm_reverse_transliterate", RES, P, P)
nc = fn("disarm_normalize_confusables_opts", RES, P, P, P)
norm = fn("disarm_normalize", RES, P, P)
s1 = {
    n: fn("disarm_" + n, STR, P)
    for n in (
        "strip_accents",
        "fold_case",
        "collapse_whitespace",
        "strip_control_chars",
        "strip_zero_width_chars",
        "strip_bidi",
        "strip_tags",
        "strip_variation_selectors",
        "strip_noncharacters",
        "strip_pua",
        "strip_format",
        "inspect_auto_lang",
    )
}
b1 = {
    n: fn("disarm_" + n, BOOL, P)
    for n in (
        "is_case_fold_stable",
        "is_mixed_script",
        "has_bidi_conflict",
        "has_bidi_control",
        "is_suspicious_hostname",
    )
}
demojize = fn("disarm_demojize", STR, P, C.c_bool)
replace_emoji = fn("disarm_replace_emoji", STR, P, P)
pol = {
    n: fn("disarm_" + n, RES, P, P)
    for n in (
        "canonicalize_opts",
        "canonicalize_strict_opts",
        "strip_obfuscation_opts",
        "skeleton_key",
    )
}
search_key = fn("disarm_search_key_opts", RES, P, P, P)
sort_key = fn("disarm_sort_key_opts", RES, P, P, P)
catalog_key = fn("disarm_catalog_key_opts", RES, P, P, C.c_bool, P)
ah = fn("disarm_analyze_hostname_opts", STR, P, C.c_bool)
glen = fn("disarm_grapheme_len", U64, P)
tw = fn("disarm_terminal_width", U64, P, C.c_bool)
is_canonical = fn("disarm_is_canonical", I8, P, P)
mln = fn("disarm_ml_normalize", RES, P, P, P, C.c_bool)
sfn = fn("disarm_sanitize_filename", RES, P, P, C.c_size_t, P, P, C.c_bool)
ia = fn("disarm_inspect_anomalies", STR, P, P)
ed = fn("disarm_edit_distance", USIZE, P, P)
fuc = fn("disarm_find_unmapped_confusables", RES, P, P)


def host(j: str) -> Rec:
    a = json.loads(j)
    return Rec(
        *(
            a[k]
            for k in (
                "suspicious",
                "scripts",
                "mixed_script",
                "has_confusables",
                "bidi_conflict",
                "bidi_control",
                "has_invisible",
                "compat_fold",
                "cross_label_script",
                "label_scripts",
                "whole_script_confusable",
                "label_whole_script_confusable",
                "canonical",
            )
        )
    )


def anomalies(j: str) -> Rec:
    a = json.loads(j)
    return Rec(
        a["anomalous"],
        a["kinds"],
        [
            Rec(f["kind"], f["token"], f["start"], f["end"], f["detail"], f["reason"])
            for f in a["findings"]
        ],
        a["reason"],
    )


def tri(v: int) -> bool:
    if v == -1:
        raise Err("c", "unknown preset")
    return bool(v)


CASES: dict[str, Callable[[str], Any]] = {
    "tr": lambda t: tr(t),
    "tr_iso9": lambda t: tr_opts(t, "strict_iso9", None),
    "tr_gost": lambda t: tr_opts(t, "gost7034", None),
    "tr_de": lambda t: tr_opts(t, "default", "de"),
    "tr_auto": lambda t: tr_opts(t, "default", "auto"),
    "tr_uk": lambda t: tr_opts(t, "default", "uk"),
    "tr_ja": lambda t: tr_opts(t, "default", "ja"),
    "tr_bad": lambda t: tr_opts(t, "default", "xx"),
    "nc_lat": lambda t: nc(t, "latin", "numeric"),
    "nc_lat_tr39": lambda t: nc(t, "latin", "tr39"),
    "nc_lat_pres": lambda t: nc(t, "latin", "preserve"),
    "nc_cyr": lambda t: nc(t, "cyrillic", "numeric"),
    "nc_ara": lambda t: nc(t, "arabic", "numeric"),
    "nc_heb": lambda t: nc(t, "hebrew", "numeric"),
    "sa": lambda t: s1["strip_accents"](t),
    "fc": lambda t: s1["fold_case"](t),
    "cfs": lambda t: b1["is_case_fold_stable"](t),
    "dj": lambda t: demojize(t, False),
    "dj_sm": lambda t: demojize(t, True),
    "re_empty": lambda t: replace_emoji(t, ""),
    "re_sp": lambda t: replace_emoji(t, " "),
    "cw": lambda t: s1["collapse_whitespace"](t),
    "scc": lambda t: s1["strip_control_chars"](t),
    "szw": lambda t: s1["strip_zero_width_chars"](t),
    "sbd": lambda t: s1["strip_bidi"](t),
    "stg": lambda t: s1["strip_tags"](t),
    "svs": lambda t: s1["strip_variation_selectors"](t),
    "snc": lambda t: s1["strip_noncharacters"](t),
    "spua": lambda t: s1["strip_pua"](t),
    "can": lambda t: pol["canonicalize_opts"](t, "numeric"),
    "can_tr39": lambda t: pol["canonicalize_opts"](t, "tr39"),
    "can_pres": lambda t: pol["canonicalize_opts"](t, "preserve"),
    "cans": lambda t: pol["canonicalize_strict_opts"](t, "numeric"),
    "sfmt": lambda t: s1["strip_format"](t),
    "sobf": lambda t: pol["strip_obfuscation_opts"](t, "numeric"),
    "sobf_tr39": lambda t: pol["strip_obfuscation_opts"](t, "tr39"),
    "sk": lambda t: search_key(t, None, "numeric"),
    "sk_de": lambda t: search_key(t, "de", "numeric"),
    "sok": lambda t: sort_key(t, None, "numeric"),
    "ck": lambda t: catalog_key(t, None, False, "numeric"),
    "ck_iso": lambda t: catalog_key(t, None, True, "numeric"),
    "skel": lambda t: pol["skeleton_key"](t, "numeric"),
    "skel_tr39": lambda t: pol["skeleton_key"](t, "tr39"),
    "nfc": lambda t: norm(t, "NFC"),
    "nfd": lambda t: norm(t, "NFD"),
    "nfkc": lambda t: norm(t, "NFKC"),
    "nfkd": lambda t: norm(t, "NFKD"),
    "mix": lambda t: b1["is_mixed_script"](t),
    "bconf": lambda t: b1["has_bidi_conflict"](t),
    "bctl": lambda t: b1["has_bidi_control"](t),
    "susp": lambda t: b1["is_suspicious_hostname"](t),
    "ah": lambda t: host(ah(t, False)),
    "ah_c": lambda t: host(ah(t, True)),
    "glen": lambda t: glen(t),
    "tw": lambda t: tw(t, False),
    "tw_amb": lambda t: tw(t, True),
    "ial": lambda t: (
        lambda a: Rec(a["script"], a["chosen_lang"], a["reason"], a["discriminators_hit"])
    )(json.loads(s1["inspect_auto_lang"](t))),
    "iscan": lambda t: tri(is_canonical(t, "canonicalize")),
    "mln": lambda t: mln(t, None, "cldr", True),
    "mln_nofold": lambda t: mln(t, None, "cldr", False),
    "sfn": lambda t: sfn(t, "_", 255, "universal", None, True),
    "ia": lambda t: anomalies(ia(t, "[]")),
    "ed": lambda t: ed(t, "paypal"),
    "fuc": lambda t: [Rec(u["char"], u["offset"]) for u in json.loads(fuc(t, "latin"))],
    "rv_ru": lambda t: rv(t, "ru"),
    "rv_el": lambda t: rv(t, "el"),
    "rv_uk": lambda t: rv(t, "uk"),
}

if __name__ == "__main__":
    main(CASES, skip=lambda t: "\x00" in t)
