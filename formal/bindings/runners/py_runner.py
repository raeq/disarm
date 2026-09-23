"""Harness runner for the Python binding (the public `disarm` package)."""

from __future__ import annotations

import functools
import os
import sys
from collections.abc import Callable
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from proto import Err, Rec, main  # noqa: E402

import disarm  # noqa: E402


def guard(fn: Callable[[str], Any]) -> Callable[[str], Any]:
    @functools.wraps(fn)
    def wrapper(t: str) -> Any:
        try:
            return fn(t)
        except disarm.InvalidArgumentError as e:
            raise Err("inv", str(e)) from None
        except disarm.DisarmError as e:
            raise Err("err", str(e)) from None
        except Exception as e:  # noqa: BLE001 - anything else is a finding
            raise Err("py:" + type(e).__name__, str(e)) from None

    return wrapper


def host(a: Any) -> Rec:
    return Rec(
        a.suspicious,
        list(a.scripts),
        a.mixed_script,
        a.has_confusables,
        a.bidi_conflict,
        a.bidi_control,
        a.has_invisible,
        a.compat_fold,
        a.cross_label_script,
        [list(x) for x in a.label_scripts],
        a.whole_script_confusable,
        list(a.label_whole_script_confusable),
        a.canonical,
    )


def anomalies(r: Any) -> Rec:
    return Rec(
        r.anomalous,
        [str(k) for k in r.kinds],
        [Rec(str(f.kind), f.token, f.start, f.end, f.detail, f.reason) for f in r.findings],
        r.reason,
    )


def sval(x: Any) -> str:
    return x.value if hasattr(x, "value") else str(x)


d = disarm
CASES: dict[str, Callable[[str], Any]] = {
    "tr": lambda t: d.transliterate(t),
    "tr_iso9": lambda t: d.transliterate(t, strict_iso9=True),
    "tr_gost": lambda t: d.transliterate(t, gost7034=True),
    "tr_de": lambda t: d.transliterate(t, lang="de"),
    "tr_auto": lambda t: d.transliterate(t, lang="auto"),
    "tr_uk": lambda t: d.transliterate(t, lang="uk"),
    "tr_ja": lambda t: d.transliterate(t, lang="ja"),
    "tr_bad": lambda t: d.transliterate(t, lang="xx"),
    "nc_lat": lambda t: d.normalize_confusables(t, target_script="latin"),
    "nc_lat_tr39": lambda t: d.normalize_confusables(t, target_script="latin", digit_policy="tr39"),
    "nc_lat_pres": lambda t: d.normalize_confusables(
        t, target_script="latin", digit_policy="preserve"
    ),
    "nc_cyr": lambda t: d.normalize_confusables(t, target_script="cyrillic"),
    "nc_ara": lambda t: d.normalize_confusables(t, target_script="arabic"),
    "nc_heb": lambda t: d.normalize_confusables(t, target_script="hebrew"),
    "sa": lambda t: d.strip_accents(t),
    "fc": lambda t: d.fold_case(t),
    "cfs": lambda t: d.is_case_fold_stable(t),
    "dj": lambda t: d.demojize(t),
    "dj_sm": lambda t: d.demojize(t, strip_modifiers=True),
    "re_empty": lambda t: d.replace_emoji(t, ""),
    "re_sp": lambda t: d.replace_emoji(t, " "),
    "cw": lambda t: d.collapse_whitespace(t),
    "scc": lambda t: d.strip_control_chars(t),
    "szw": lambda t: d.strip_zero_width_chars(t),
    "sbd": lambda t: d.strip_bidi(t),
    "stg": lambda t: d.strip_tags(t),
    "svs": lambda t: d.strip_variation_selectors(t),
    "snc": lambda t: d.strip_noncharacters(t),
    "spua": lambda t: d.strip_pua(t),
    "can": lambda t: d.canonicalize(t),
    "can_tr39": lambda t: d.canonicalize(t, digit_policy="tr39"),
    "can_pres": lambda t: d.canonicalize(t, digit_policy="preserve"),
    "cans": lambda t: d.canonicalize_strict(t),
    "sfmt": lambda t: d.strip_format(t),
    "sobf": lambda t: d.strip_obfuscation(t),
    "sobf_tr39": lambda t: d.strip_obfuscation(t, digit_policy="tr39"),
    "sk": lambda t: d.search_key(t),
    "sk_de": lambda t: d.search_key(t, lang="de"),
    "sok": lambda t: d.sort_key(t),
    "ck": lambda t: d.catalog_key(t),
    "ck_iso": lambda t: d.catalog_key(t, strict_iso9=True),
    "skel": lambda t: d.skeleton_key(t),
    "skel_tr39": lambda t: d.skeleton_key(t, digit_policy="tr39"),
    "nfc": lambda t: d.normalize(t, form="NFC"),
    "nfd": lambda t: d.normalize(t, form="NFD"),
    "nfkc": lambda t: d.normalize(t, form="NFKC"),
    "nfkd": lambda t: d.normalize(t, form="NFKD"),
    "isn_nfc": lambda t: d.is_normalized(t, form="NFC"),
    "mix": lambda t: d.is_mixed_script(t),
    "bconf": lambda t: d.has_bidi_conflict(t),
    "bctl": lambda t: d.has_bidi_control(t),
    "susp": lambda t: d.is_suspicious_hostname(t)[0],
    "ah": lambda t: host(d.is_suspicious_hostname(t)[1]),
    "ah_c": lambda t: host(d.is_suspicious_hostname(t, contractions=True)[1]),
    "glen": lambda t: d.grapheme_len(t),
    "gsplit": lambda t: d.grapheme_split(t),
    "gtrunc1": lambda t: d.grapheme_truncate(t, 1),
    "tw": lambda t: d.terminal_width(t),
    "tw_amb": lambda t: d.terminal_width(t, ambiguous_wide=True),
    "ial": lambda t: (
        lambda a: Rec(a["script"], a["chosen_lang"], a["reason"], list(a["discriminators_hit"]))
    )(d.inspect_auto_lang(t)),
    "ds": lambda t: [sval(x) for x in d.detect_scripts(t)],
    "iscan": lambda t: d.is_canonical(t),
    "mln": lambda t: d.ml_normalize(t),
    "mln_nofold": lambda t: d.ml_normalize(t, fold_case=False),
    "sfn": lambda t: d.sanitize_filename(t),
    "ia": lambda t: anomalies(d.inspect_anomalies(t)),
    "ha": lambda t: d.has_anomalies(t),
    "ed": lambda t: d.edit_distance(t, "paypal"),
    "fu": lambda t: [Rec(c, o) for c, o in d.find_untranslatable(t)],
    "fuc": lambda t: [Rec(c, o) for c, o in d.find_unmapped_confusables(t)],
    "rv_ru": lambda t: d.transliterate(t, target="ru"),
    "rv_el": lambda t: d.transliterate(t, target="el"),
    "rv_uk": lambda t: d.transliterate(t, target="uk"),
    "slug": lambda t: d.slugify(t),
    "zs": lambda t: d.strip_zalgo(t, max_marks=3),
    "zi": lambda t: d.is_zalgo(t, threshold=3),
    "isconf": lambda t: d.is_confusable(t),
}
CASES = {k: guard(v) for k, v in CASES.items()}

if __name__ == "__main__":
    main(CASES)
