#!/usr/bin/env python3
"""Character-level correctness diff: translit vs Unidecode vs anyascii.

For each of the 65 supported languages, takes ~4k characters of real text
(repeating the canonical sample), runs all three libraries, and reports:

1. Characters where outputs differ
2. Coverage: which library maps more characters (vs returning '?' or empty)
3. Language-aware differences (e.g., German Ü→Ue vs Ü→U)

Usage:
    python benchmarks/diff_vs_unidecode.py                  # summary
    python benchmarks/diff_vs_unidecode.py --detail         # per-char diffs
    python benchmarks/diff_vs_unidecode.py --markdown       # markdown report
    python benchmarks/diff_vs_unidecode.py --markdown > docs/architecture/transliteration-comparison.md
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

import translit as tr

try:
    from unidecode import unidecode
except ImportError:
    unidecode = None

try:
    from anyascii import anyascii
except ImportError:
    anyascii = None

# ---------------------------------------------------------------------------
# Language samples (from test_transliterate.py)
# ---------------------------------------------------------------------------

LANG_SAMPLES: dict[str, tuple[str, str]] = {
    "bg": ("Република България е държава в Югоизточна Европа", "Bulgarian"),
    "ca": ("Catalunya és una comunitat autònoma d'Espanya", "Catalan"),
    "cs": ("Česká republika je stát ve střední Evropě", "Czech"),
    "cy": ("Cymru yw gwlad sy'n rhan o'r Deyrnas Unedig", "Welsh"),
    "da": ("København er Danmarks hovedstad og største by", "Danish"),
    "de": ("Die Bundesrepublik Deutschland ist ein Bundesstaat in Mitteleuropa", "German"),
    "el": ("Η Ελληνική Δημοκρατία είναι χώρα της νοτιοανατολικής Ευρώπης", "Greek"),
    "es": ("España es un país soberano transcontinental", "Spanish"),
    "et": ("Eesti Vabariik on riik Põhja-Euroopas Läänemere ääres", "Estonian"),
    "fi": ("Suomen tasavalta on valtio Pohjois-Euroopassa", "Finnish"),
    "fr": ("La République française est un État transcontinental", "French"),
    "ga": ("Éire nó Poblacht na hÉireann is tír í", "Irish"),
    "hr": ("Republika Hrvatska je država u srednjoj Europi", "Croatian"),
    "hu": ("Magyarország közép-európai ország", "Hungarian"),
    "is": ("Ísland er eyríki á norðanverðum Atlantshafi", "Icelandic"),
    "it": ("La Repubblica Italiana è uno Stato membro dell'Unione europea", "Italian"),
    "lt": ("Lietuvos Respublika yra valstybė šiaurės Europoje", "Lithuanian"),
    "lv": ("Latvijas Republika ir valsts Ziemeļeiropā", "Latvian"),
    "mt": ("Ir-Repubblika ta' Malta hija stat gżejjer fil-Mediterran", "Maltese"),
    "nl": ("Het Koninkrijk der Nederlanden is een staat in West-Europa", "Dutch"),
    "no": ("Kongeriket Norge er et nordisk land i Skandinavia", "Norwegian"),
    "pl": ("Rzeczpospolita Polska jest państwem w Europie Środkowej", "Polish"),
    "pt": ("A República Portuguesa é um país situado no sudoeste da Europa", "Portuguese"),
    "ro": ("România este un stat situat în sud-estul Europei", "Romanian"),
    "sk": ("Slovenská republika je štát v strednej Európe", "Slovak"),
    "sl": ("Republika Slovenija je država v srednji Evropi", "Slovenian"),
    "sq": ("Republika e Shqipërisë është një shtet në Europën Juglindore", "Albanian"),
    "sr": ("Република Србија је држава у Југоисточној Европи", "Serbian"),
    "sv": ("Konungariket Sverige är ett nordiskt land på Skandinaviska halvön", "Swedish"),
    "tr": ("Türkiye Cumhuriyeti Avrupa ile Asya arasında yer alan bir ülkedir", "Turkish"),
    "uk": ("Україна є державою у Східній та Центральній Європі", "Ukrainian"),
    "vi": ("Cộng hòa xã hội chủ nghĩa Việt Nam là một quốc gia", "Vietnamese"),
    "ja": ("日本国は東アジアに位置する島国である", "Japanese"),
    "ja-kunrei": ("しちつふじ", "Japanese Kunrei"),
    "ko": ("대한민국은 동아시아에 있는 공화국이다", "Korean"),
    "zh": ("中华人民共和国是位于东亚的社会主义国家", "Chinese"),
    "ar": ("المملكة العربية السعودية دولة عربية تقع في شبه الجزيرة العربية", "Arabic"),
    "fa": ("جمهوری اسلامی ایران کشوری در خاورمیانه است", "Persian"),
    "he": ("מדינת ישראל היא מדינה במזרח התיכון", "Hebrew"),
    "hi": ("भारत गणराज्य दक्षिण एशिया में स्थित एक देश है", "Hindi"),
    "bn": ("গণপ্রজাতন্ত্রী বাংলাদেশ দক্ষিণ এশিয়ার একটি রাষ্ট্র", "Bengali"),
    "ta": ("தமிழ்நாடு இந்தியாவின் தெற்கே அமைந்துள்ள மாநிலம்", "Tamil"),
    "te": ("తెలుగు భాష ద్రావిడ భాషా కుటుంబానికి చెందిన భాష", "Telugu"),
    "gu": ("ગુજરાત ભારતનું એક રાજ્ય છે જે ભારતના પશ્ચિમ ભાગમાં", "Gujarati"),
    "kn": ("ಕರ್ನಾಟಕ ದಕ್ಷಿಣ ಭಾರತದ ಒಂದು ರಾಜ್ಯ", "Kannada"),
    "ml": ("കേരളം ഇന്ത്യയിലെ ഒരു സംസ്ഥാനമാണ്", "Malayalam"),
    "mr": ("महाराष्ट्र हे भारतातील एक राज्य आहे", "Marathi"),
    "ne": ("नेपाल एशियाको एक स्वतन्त्र देश हो", "Nepali"),
    "or": ("ଓଡ଼ିଶା ଭାରତର ପୂର୍ବ ଉପକୂଳରେ ଅବସ୍ଥିତ", "Odia"),
    "pa": ("ਪੰਜਾਬ ਭਾਰਤ ਦਾ ਇੱਕ ਰਾਜ ਹੈ", "Punjabi"),
    "sa": ("संस्कृतम् जगतः एका प्राचीनतमा भाषा", "Sanskrit"),
    "as": ("অসম ভাৰতৰ উত্তৰ পূৰ্বাঞ্চলৰ এখন ৰাজ্য", "Assamese"),
    "hy": ("Հայաստան Հանրdelays", "Armenian"),
    "ka": ("საქართველო სახელმწიფოა აღმოსავლეთ ევროპაში", "Georgian"),
    "si": ("ශ්‍රී ලංකා ප්‍රජාතාන්ත්‍රික සමාජවාදී ජනරජය", "Sinhala"),
    "th": ("ประเทศไทยเป็นรัฐชาติอันตั้งอยู่ในเอเชียตะวันออกเฉียงใต้", "Thai"),
    "lo": ("ສາທາລະນະລັດ ປະຊາທິປະໄຕ ປະຊາຊົນລາວ", "Lao"),
    "km": ("ព្រះរាជាណាចក្រកម្ពុជា ជាប្រទេសមួយ", "Khmer"),
    "my": ("မြန်မာနိုင်ငံသည် အရှေ့တောင်အာရှတွင်", "Myanmar"),
    "bo": ("བོད་རང་སྐྱོང་ལྗོངས་ནི་རྒྱ་ནག་གི་ཁོངས་གཏོགས", "Tibetan"),
    "am": (
        "የኢትዮጵያ ፌዴራላዊ ዲሞክራሲያዊ ሪፐብሊክ መንግሥት "
        "የፌዴራሉ መንግስት ሁለት ምክር ቤቶች ሲኖሩት",
        "Amharic",
    ),
    "ru": ("Российская Федерация является демократическим федеративным государством", "Russian"),
    "dv": ("ދިވެހިރާއްޖެ", "Dhivehi"),
    "jv": ("\uA990\uA99F\uA9AA\uA9A3\uA9A8", "Javanese"),
    "mn": ("\u182E\u1823\u1829\u182D\u1823\u182F", "Mongolian"),
}

TARGET_CHARS = 4000


@dataclass
class CharDiff:
    """A single character where libraries produce different output."""
    char: str
    codepoint: int
    name: str
    translit_out: str
    unidecode_out: str | None
    anyascii_out: str | None


@dataclass
class LangReport:
    """Comparison report for one language."""
    lang: str
    description: str
    total_non_ascii: int = 0
    translit_mapped: int = 0
    unidecode_mapped: int = 0
    anyascii_mapped: int = 0
    diffs_translit_vs_unidecode: list[CharDiff] = field(default_factory=list)
    diffs_translit_vs_anyascii: list[CharDiff] = field(default_factory=list)
    translit_only: int = 0  # mapped by translit but not unidecode
    unidecode_only: int = 0  # mapped by unidecode but not translit


def is_mapped(output: str, original: str) -> bool:
    """Check if a library actually mapped the character (vs returning it unchanged or '?')."""
    if not output or output == original:
        return False
    if all(c in ("[", "]", "?") for c in output):
        return False
    return True


def expand_sample(text: str, target: int = TARGET_CHARS) -> str:
    """Repeat sample text to reach ~target characters."""
    if len(text) >= target:
        return text[:target]
    repeats = (target // len(text)) + 1
    return (text * repeats)[:target]


def unique_non_ascii_chars(text: str) -> list[str]:
    """Extract unique non-ASCII characters, preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for ch in text:
        if ord(ch) > 127 and ch not in seen:
            seen.add(ch)
            result.append(ch)
    return result


def compare_char(ch: str, lang: str) -> CharDiff:
    """Compare transliteration of a single character across libraries."""
    t_out = tr.transliterate(ch, lang=lang, errors="ignore")
    u_out = unidecode(ch) if unidecode else None
    a_out = anyascii(ch) if anyascii else None
    try:
        name = unicodedata.name(ch)
    except ValueError:
        name = f"U+{ord(ch):04X}"
    return CharDiff(
        char=ch,
        codepoint=ord(ch),
        name=name,
        translit_out=t_out,
        unidecode_out=u_out,
        anyascii_out=a_out,
    )


def analyze_language(lang: str, sample: str, desc: str) -> LangReport:
    """Run full comparison for one language."""
    text = expand_sample(sample)
    chars = unique_non_ascii_chars(text)

    report = LangReport(lang=lang, description=desc, total_non_ascii=len(chars))

    for ch in chars:
        diff = compare_char(ch, lang)

        t_mapped = is_mapped(diff.translit_out, ch)
        u_mapped = is_mapped(diff.unidecode_out, ch) if diff.unidecode_out is not None else False
        a_mapped = is_mapped(diff.anyascii_out, ch) if diff.anyascii_out is not None else False

        if t_mapped:
            report.translit_mapped += 1
        if u_mapped:
            report.unidecode_mapped += 1
        if a_mapped:
            report.anyascii_mapped += 1

        if t_mapped and not u_mapped:
            report.translit_only += 1
        if u_mapped and not t_mapped:
            report.unidecode_only += 1

        # Record diffs where both map but produce different output
        if t_mapped and u_mapped and diff.translit_out != diff.unidecode_out:
            report.diffs_translit_vs_unidecode.append(diff)
        if t_mapped and a_mapped and diff.translit_out != diff.anyascii_out:
            report.diffs_translit_vs_anyascii.append(diff)

    return report


def print_summary(reports: list[LangReport]) -> None:
    """Print summary table to stdout."""
    print(f"{'Lang':<12} {'Description':<16} {'Chars':>5} {'translit':>8} "
          f"{'Unidec':>6} {'anyasc':>6} {'t-only':>6} {'u-only':>6} {'diffs':>5}")
    print("-" * 90)

    totals = defaultdict(int)
    for r in reports:
        diffs = len(r.diffs_translit_vs_unidecode)
        print(f"{r.lang:<12} {r.description:<16} {r.total_non_ascii:>5} "
              f"{r.translit_mapped:>8} {r.unidecode_mapped:>6} {r.anyascii_mapped:>6} "
              f"{r.translit_only:>6} {r.unidecode_only:>6} {diffs:>5}")
        totals["chars"] += r.total_non_ascii
        totals["translit"] += r.translit_mapped
        totals["unidecode"] += r.unidecode_mapped
        totals["anyascii"] += r.anyascii_mapped
        totals["t_only"] += r.translit_only
        totals["u_only"] += r.unidecode_only
        totals["diffs"] += diffs

    print("-" * 90)
    print(f"{'TOTAL':<12} {'':<16} {totals['chars']:>5} "
          f"{totals['translit']:>8} {totals['unidecode']:>6} {totals['anyascii']:>6} "
          f"{totals['t_only']:>6} {totals['u_only']:>6} {totals['diffs']:>5}")


def print_detail(reports: list[LangReport]) -> None:
    """Print per-character diffs."""
    for r in reports:
        if not r.diffs_translit_vs_unidecode:
            continue
        print(f"\n=== {r.lang} ({r.description}) — {len(r.diffs_translit_vs_unidecode)} differences ===")
        for d in r.diffs_translit_vs_unidecode[:50]:
            print(f"  {d.char} U+{d.codepoint:04X} {d.name:<40} "
                  f"translit={d.translit_out!r:<12} unidecode={d.unidecode_out!r:<12}"
                  + (f" anyascii={d.anyascii_out!r}" if d.anyascii_out is not None else ""))
        if len(r.diffs_translit_vs_unidecode) > 50:
            print(f"  ... and {len(r.diffs_translit_vs_unidecode) - 50} more")


def print_markdown(reports: list[LangReport]) -> None:
    """Print full markdown report."""
    print("# Transliteration Comparison: translit vs Unidecode vs anyascii")
    print()
    print("Character-level correctness comparison across all 65 supported languages.")
    print("Each language tested with ~4,000 characters of real-world text.")
    print()
    print("## Methodology")
    print()
    print("For each language:")
    print("1. Canonical sample text is expanded to ~4k characters")
    print("2. Unique non-ASCII characters are extracted")
    print("3. Each character is transliterated by all three libraries")
    print("4. \"Mapped\" means the library produced meaningful ASCII output")
    print("   (not empty, not `[?]`, not the original character)")
    print()
    print("## Summary")
    print()
    print("| Lang | Description | Unique chars | translit | Unidecode | anyascii | translit-only | Unidecode-only | Output diffs |")
    print("|------|-------------|-------------|----------|-----------|----------|---------------|----------------|-------------|")

    totals = defaultdict(int)
    for r in reports:
        diffs = len(r.diffs_translit_vs_unidecode)
        print(f"| {r.lang} | {r.description} | {r.total_non_ascii} | "
              f"{r.translit_mapped} | {r.unidecode_mapped} | {r.anyascii_mapped} | "
              f"{r.translit_only} | {r.unidecode_only} | {diffs} |")
        totals["chars"] += r.total_non_ascii
        totals["translit"] += r.translit_mapped
        totals["unidecode"] += r.unidecode_mapped
        totals["anyascii"] += r.anyascii_mapped
        totals["t_only"] += r.translit_only
        totals["u_only"] += r.unidecode_only
        totals["diffs"] += diffs

    print(f"| **TOTAL** | | **{totals['chars']}** | "
          f"**{totals['translit']}** | **{totals['unidecode']}** | **{totals['anyascii']}** | "
          f"**{totals['t_only']}** | **{totals['u_only']}** | **{totals['diffs']}** |")

    # Detail sections for languages with interesting diffs
    print()
    print("## Notable Differences")
    print()

    for r in reports:
        if not r.diffs_translit_vs_unidecode and r.translit_only == 0:
            continue
        print(f"### {r.lang} — {r.description}")
        print()
        if r.translit_only > 0 or r.unidecode_only > 0:
            print(f"Coverage: translit maps {r.translit_mapped}/{r.total_non_ascii} chars, "
                  f"Unidecode maps {r.unidecode_mapped}/{r.total_non_ascii}. "
                  f"**{r.translit_only}** mapped only by translit, "
                  f"**{r.unidecode_only}** mapped only by Unidecode.")
            print()
        if r.diffs_translit_vs_unidecode:
            print("| Char | Codepoint | Name | translit | Unidecode | anyascii |")
            print("|------|-----------|------|----------|-----------|----------|")
            for d in r.diffs_translit_vs_unidecode[:30]:
                a_col = f"`{d.anyascii_out}`" if d.anyascii_out else "—"
                print(f"| {d.char} | U+{d.codepoint:04X} | {d.name} | "
                      f"`{d.translit_out}` | `{d.unidecode_out}` | {a_col} |")
            if len(r.diffs_translit_vs_unidecode) > 30:
                remaining = len(r.diffs_translit_vs_unidecode) - 30
                print(f"| | | *...{remaining} more differences* | | | |")
            print()

    print("## Key Takeaways")
    print()
    print(f"- **Total unique non-ASCII characters tested**: {totals['chars']}")
    print(f"- **translit coverage**: {totals['translit']}/{totals['chars']} "
          f"({100*totals['translit']/max(totals['chars'],1):.1f}%)")
    print(f"- **Unidecode coverage**: {totals['unidecode']}/{totals['chars']} "
          f"({100*totals['unidecode']/max(totals['chars'],1):.1f}%)")
    print(f"- **anyascii coverage**: {totals['anyascii']}/{totals['chars']} "
          f"({100*totals['anyascii']/max(totals['chars'],1):.1f}%)")
    print(f"- **Characters mapped only by translit**: {totals['t_only']}")
    print(f"- **Characters mapped only by Unidecode**: {totals['u_only']}")
    print(f"- **Different output (both mapped)**: {totals['diffs']}")
    print()
    print("---")
    print()
    print("*Generated by `benchmarks/diff_vs_unidecode.py`*")


def main():
    parser = argparse.ArgumentParser(description="Transliteration correctness comparison")
    parser.add_argument("--detail", action="store_true", help="Show per-character diffs")
    parser.add_argument("--markdown", action="store_true", help="Output markdown report")
    args = parser.parse_args()

    if not unidecode:
        print("WARNING: Unidecode not installed (pip install Unidecode)", file=sys.stderr)
    if not anyascii:
        print("WARNING: anyascii not installed (pip install anyascii)", file=sys.stderr)

    reports = []
    for lang, (sample, desc) in LANG_SAMPLES.items():
        report = analyze_language(lang, sample, desc)
        reports.append(report)

    if args.markdown:
        print_markdown(reports)
    else:
        print_summary(reports)
        if args.detail:
            print_detail(reports)


if __name__ == "__main__":
    main()
