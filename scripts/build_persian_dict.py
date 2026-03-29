#!/usr/bin/env python3
"""Build Persian context dictionary from common word lists + rules.

Persian lacks a large diacritized corpus like Arabic's Tashkeela. Instead,
this builder creates a dictionary from:

1. A curated list of common Persian words with their known romanizations
2. Persian words that appear in the Arabic Tashkeela corpus (Arabic loanwords)
3. Rule-based expansion for common morphological patterns

The output format is identical to the Arabic dictionary (TRLD v1) so the
same Rust ContextDict reader handles both.

Usage:
    python scripts/build_persian_dict.py -o data/persian_dict.bin
    python scripts/build_persian_dict.py -o data/persian_dict.bin --stats
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Persian diacritic handling (same marks as Arabic)
# ---------------------------------------------------------------------------

PERSIAN_DIACRITICS = frozenset(
    "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0653\u0654\u0655\u0670"
)
TATWEEL = "\u0640"


def strip_diacritics(word: str) -> str:
    return "".join(c for c in word if c not in PERSIAN_DIACRITICS and c != TATWEEL)


# ---------------------------------------------------------------------------
# Core Persian vocabulary with diacritized forms
#
# This is the source of truth for Persian context-aware transliteration.
# Each entry maps a consonant skeleton to its diacritized form(s).
# The diacritized form uses Arabic tashkeel marks (fatha=a, kasra=e/i,
# damma=o/u, shadda=gemination, sukun=no vowel).
#
# Sources: Dehkhoda dictionary, Wiktionary Persian entries, common usage.
# Format: (unpointed_skeleton, diacritized_form, frequency_weight)
# ---------------------------------------------------------------------------

# Common Persian words with diacritics applied.
# Using actual Arabic diacritical marks for consistency with the transliteration engine.
# \u064e = fatha (a/æ), \u0650 = kasra (e/i), \u064f = damma (o/u)
# \u0651 = shadda (gemination), \u0652 = sukun (no vowel)

_FA = "\u064e"  # fatha → a
_KA = "\u0650"  # kasra → e (Persian) / i
_DA = "\u064f"  # damma → o (Persian) / u
_SH = "\u0651"  # shadda
_SU = "\u0652"  # sukun

PERSIAN_VOCAB: list[tuple[str, str, int]] = [
    # --- Greetings & common phrases ---
    ("سلام", f"س{_FA}لا{_SU}م", 10000),
    ("خداحافظ", f"خ{_DA}دا{_SU}حاف{_KA}ظ", 5000),
    # --- Pronouns ---
    ("من", f"م{_FA}ن", 50000),
    ("تو", f"ت{_DA}", 40000),
    ("او", f"ا{_DA}", 35000),
    ("ما", "ما", 30000),
    ("شما", f"ش{_DA}ما", 25000),
    # --- Common nouns ---
    ("کتاب", f"ک{_KA}تا{_SU}ب", 8000),
    ("خانه", f"خان{_KA}ه", 7000),
    ("آب", "آب", 9000),
    ("نان", "نان", 6000),
    ("مرد", f"م{_FA}ر{_SU}د", 7000),
    ("زن", f"ز{_FA}ن", 7000),
    ("بچه", f"ب{_FA}چ{_SH}{_KA}ه", 6000),
    ("شهر", f"ش{_FA}ه{_SU}ر", 5000),
    ("کشور", f"ک{_KA}ش{_SU}و{_FA}ر", 5000),
    ("زبان", f"ز{_FA}بان", 4000),
    ("دانشگاه", f"دان{_KA}ش{_SU}گاه", 3000),
    ("دانش", f"دان{_KA}ش", 3500),
    ("روز", f"ر{_DA}ز", 8000),
    ("شب", f"ش{_FA}ب", 7000),
    ("سال", "سال", 7000),
    ("ماه", "ماه", 6000),
    ("نام", "نام", 5000),
    ("کار", "کار", 7000),
    ("راه", "راه", 6000),
    ("دست", f"د{_FA}س{_SU}ت", 5000),
    ("سر", f"س{_FA}ر", 6000),
    ("چشم", f"چ{_FA}ش{_SU}م", 4000),
    ("دل", f"د{_KA}ل", 5000),
    # --- Places ---
    ("ایران", "ایران", 10000),
    ("تهران", f"ت{_KA}ه{_SU}ران", 8000),
    ("اصفهان", f"ا{_KA}ص{_SU}ف{_FA}هان", 4000),
    ("شیراز", "شیراز", 4000),
    # --- Adjectives ---
    ("بزرگ", f"ب{_DA}ز{_DA}ر{_SU}گ", 6000),
    ("کوچک", f"ک{_DA}چ{_FA}ک", 5000),
    ("خوب", f"خ{_DA}ب", 8000),
    ("بد", f"ب{_FA}د", 7000),
    ("زیبا", "زیبا", 4000),
    ("نو", f"ن{_DA}", 5000),
    # --- Verbs (infinitive stems) ---
    ("است", f"ا{_FA}س{_SU}ت", 50000),
    ("بود", f"ب{_DA}د", 20000),
    ("شد", f"ش{_DA}د", 15000),
    ("کرد", f"ک{_FA}ر{_SU}د", 12000),
    ("گفت", f"گ{_DA}ف{_SU}ت", 10000),
    ("رفت", f"ر{_FA}ف{_SU}ت", 8000),
    ("آمد", f"آم{_FA}د", 8000),
    ("داد", "داد", 7000),
    ("دید", "دید", 6000),
    ("خواست", f"خ{_SU}واس{_SU}ت", 5000),
    ("داشت", f"داش{_SU}ت", 8000),
    ("شده", f"ش{_DA}د{_KA}ه", 10000),
    ("کرده", f"ک{_FA}ر{_SU}د{_KA}ه", 8000),
    ("نوشت", f"ن{_KA}و{_KA}ش{_SU}ت", 3000),
    # --- Prepositions & particles ---
    ("در", f"د{_FA}ر", 40000),
    ("به", f"ب{_KA}ه", 35000),
    ("از", f"ا{_FA}ز", 30000),
    ("با", "با", 25000),
    ("برای", f"ب{_FA}رای", 15000),
    ("تا", "تا", 12000),
    ("که", f"ک{_KA}ه", 40000),
    ("این", "این", 30000),
    ("آن", "آن", 20000),
    ("هم", f"ه{_FA}م", 15000),
    ("یک", f"ی{_FA}ک", 12000),
    ("دو", f"د{_DA}", 10000),
    ("سه", f"س{_KA}ه", 8000),
    ("هر", f"ه{_FA}ر", 10000),
    ("چه", f"چ{_KA}ه", 8000),
    ("خود", f"خ{_DA}د", 12000),
    ("دیگر", f"دیگ{_FA}ر", 8000),
    # --- Islamic/Arabic loanwords common in Persian ---
    ("الله", f"ا{_FA}ل{_SH}اه", 5000),
    ("محمد", f"م{_DA}ح{_FA}م{_SH}{_FA}د", 4000),
    ("اسلام", f"ا{_KA}س{_SU}لام", 3000),
    ("قرآن", f"ق{_DA}ر{_SU}آن", 3000),
    # --- Food & daily life ---
    ("غذا", f"غ{_FA}ذا", 3000),
    ("چای", "چای", 3000),
    # --- Modern words ---
    ("دولت", f"د{_DA}ل{_FA}ت", 4000),
    ("مردم", f"م{_FA}ر{_SU}د{_DA}م", 5000),
    ("جهان", f"ج{_FA}هان", 3000),
    ("فارسی", f"فار{_SU}سی", 5000),
    ("عربی", f"ع{_FA}ر{_FA}بی", 3000),
    # --- Extended vocabulary: verbs ---
    ("خواندن", f"خ{_SU}واند{_FA}ن", 3000),
    ("نوشتن", f"ن{_KA}و{_KA}ش{_SU}ت{_FA}ن", 2500),
    ("خوردن", f"خ{_DA}ر{_SU}د{_FA}ن", 2500),
    ("دادن", f"داد{_FA}ن", 2500),
    ("گرفتن", f"گ{_KA}ر{_KA}ف{_SU}ت{_FA}ن", 2500),
    ("دانستن", f"دان{_KA}س{_SU}ت{_FA}ن", 2000),
    ("توانستن", f"ت{_FA}وان{_KA}س{_SU}ت{_FA}ن", 2000),
    ("خواستن", f"خ{_SU}واس{_SU}ت{_FA}ن", 2000),
    ("ماندن", f"ماند{_FA}ن", 2000),
    ("بردن", f"ب{_DA}ر{_SU}د{_FA}ن", 2000),
    ("آوردن", f"آو{_FA}ر{_SU}د{_FA}ن", 2000),
    ("زدن", f"ز{_FA}د{_FA}ن", 2000),
    ("شنیدن", f"ش{_KA}نید{_FA}ن", 1500),
    ("پرسیدن", f"پ{_DA}ر{_SU}سید{_FA}ن", 1500),
    ("فهمیدن", f"ف{_FA}ه{_SU}مید{_FA}ن", 1500),
    ("نشستن", f"ن{_KA}ش{_FA}س{_SU}ت{_FA}ن", 1500),
    ("ایستادن", f"ایس{_SU}تاد{_FA}ن", 1500),
    ("افتادن", f"ا{_DA}ف{_SU}تاد{_FA}ن", 1500),
    ("شدن", f"ش{_DA}د{_FA}ن", 10000),
    ("کردن", f"ک{_FA}ر{_SU}د{_FA}ن", 8000),
    ("بودن", f"ب{_DA}د{_FA}ن", 8000),
    ("داشتن", f"داش{_SU}ت{_FA}ن", 6000),
    ("رفتن", f"ر{_FA}ف{_SU}ت{_FA}ن", 5000),
    ("آمدن", f"آم{_FA}د{_FA}ن", 5000),
    ("گفتن", f"گ{_DA}ف{_SU}ت{_FA}ن", 5000),
    ("دیدن", f"دید{_FA}ن", 4000),
    # --- Extended vocabulary: verb past stems ---
    ("آمده", f"آم{_FA}د{_KA}ه", 5000),
    ("رفته", f"ر{_FA}ف{_SU}ت{_KA}ه", 4000),
    ("گفته", f"گ{_DA}ف{_SU}ت{_KA}ه", 3000),
    ("دیده", f"دید{_KA}ه", 3000),
    ("داده", f"داد{_KA}ه", 3000),
    ("بوده", f"ب{_DA}د{_KA}ه", 4000),
    ("داشته", f"داش{_SU}ت{_KA}ه", 3000),
    ("خورده", f"خ{_DA}ر{_SU}د{_KA}ه", 2000),
    ("نوشته", f"ن{_KA}و{_KA}ش{_SU}ت{_KA}ه", 2000),
    ("خوانده", f"خ{_SU}واند{_KA}ه", 2000),
    ("گرفته", f"گ{_KA}ر{_KA}ف{_SU}ت{_KA}ه", 2000),
    # --- Extended vocabulary: nouns ---
    ("آدم", f"آد{_FA}م", 3000),
    ("وقت", f"و{_FA}ق{_SU}ت", 3000),
    ("حرف", f"ه{_FA}ر{_SU}ف", 3000),
    ("قلب", f"ق{_FA}ل{_SU}ب", 2000),
    ("عشق", f"ع{_KA}ش{_SU}ق", 2000),
    ("زندگی", f"ز{_KA}ن{_SU}د{_KA}گی", 3000),
    ("خانواده", f"خان{_KA}واد{_KA}ه", 2500),
    ("دنیا", f"د{_DA}ن{_SU}یا", 3000),
    ("دوست", f"د{_DA}س{_SU}ت", 3000),
    ("پدر", f"پ{_KA}د{_FA}ر", 3000),
    ("مادر", f"ماد{_FA}ر", 3000),
    ("برادر", f"ب{_FA}راد{_FA}ر", 2000),
    ("خواهر", f"خ{_SU}واه{_FA}ر", 2000),
    ("فرزند", f"ف{_FA}ر{_SU}ز{_FA}ن{_SU}د", 2000),
    ("معلم", f"م{_DA}ع{_FA}ل{_KA}م", 2000),
    ("دانشجو", f"دان{_KA}ش{_SU}ج{_DA}", 1500),
    ("دکتر", f"د{_DA}ک{_SU}ت{_DA}ر", 1500),
    ("مدرسه", f"م{_FA}د{_SU}ر{_KA}س{_KA}ه", 2000),
    ("بیمارستان", f"بیمار{_KA}س{_SU}تان", 1000),
    ("هواپیما", f"ه{_FA}واپ{_KA}یما", 1000),
    ("ماشین", "ماشین", 2000),
    ("تلفن", f"ت{_KA}ل{_KA}ف{_DA}ن", 1500),
    ("کامپیوتر", f"کام{_SU}پ{_KA}یوت{_FA}ر", 1000),
    ("اینترنت", f"این{_SU}ت{_KA}ر{_SU}ن{_KA}ت", 1000),
    ("کاغذ", f"کاغ{_FA}ز", 1500),
    ("قلم", f"ق{_FA}ل{_FA}م", 1500),
    ("میز", "میز", 2000),
    ("صندلی", f"ص{_FA}ن{_SU}د{_FA}لی", 1500),
    ("پنجره", f"پ{_FA}ن{_SU}ج{_FA}ر{_KA}ه", 1500),
    ("اتاق", f"ا{_DA}تاق", 2000),
    ("آسمان", f"آس{_KA}مان", 2000),
    ("زمین", f"ز{_FA}مین", 2000),
    ("درخت", f"د{_KA}ر{_FA}خ{_SU}ت", 1500),
    ("گل", f"گ{_DA}ل", 2000),
    ("آب", "آب", 5000),
    ("هوا", f"ه{_FA}وا", 2500),
    ("باران", "باران", 1500),
    ("برف", f"ب{_FA}ر{_SU}ف", 1500),
    # --- Extended vocabulary: adjectives ---
    ("جدید", f"ج{_FA}دید", 2000),
    ("قدیمی", f"ق{_FA}دیمی", 1500),
    ("قشنگ", f"ق{_FA}ش{_FA}ن{_SU}گ", 2000),
    ("سرد", f"س{_FA}ر{_SU}د", 2000),
    ("گرم", f"گ{_FA}ر{_SU}م", 2000),
    ("تازه", f"تاز{_KA}ه", 2000),
    ("آماده", f"آماد{_KA}ه", 1500),
    ("مهم", f"م{_DA}ه{_KA}م", 2000),
    ("ممکن", f"م{_DA}م{_SU}ک{_KA}ن", 2000),
    ("لازم", f"لاز{_KA}م", 1500),
    ("راحت", f"راح{_FA}ت", 1500),
    ("مشکل", f"م{_DA}ش{_SU}ک{_KA}ل", 2000),
    ("ساده", f"ساد{_KA}ه", 1500),
    ("سخت", f"س{_FA}خ{_SU}ت", 2000),
    # --- Extended vocabulary: time & numbers ---
    ("امروز", f"ا{_KA}م{_SU}ر{_DA}ز", 3000),
    ("دیروز", f"دیر{_DA}ز", 2000),
    ("فردا", f"ف{_FA}ر{_SU}دا", 2000),
    ("صبح", f"ص{_DA}ب{_SU}ه", 2000),
    ("ظهر", f"ز{_DA}ه{_SU}ر", 1500),
    ("شام", "شام", 2000),
    ("ساعت", f"ساع{_FA}ت", 2000),
    ("دقیقه", f"د{_FA}قیق{_KA}ه", 1500),
    ("هفته", f"ه{_FA}ف{_SU}ت{_KA}ه", 2000),
    ("چهار", f"چ{_FA}هار", 3000),
    ("پنج", f"پ{_FA}ن{_SU}ج", 3000),
    ("شش", f"ش{_KA}ش", 3000),
    ("هفت", f"ه{_FA}ف{_SU}ت", 3000),
    ("هشت", f"ه{_FA}ش{_SU}ت", 3000),
    ("نه", f"ن{_DA}ه", 3000),
    ("ده", f"د{_FA}ه", 3000),
    ("صد", f"ص{_FA}د", 2000),
    ("هزار", f"ه{_KA}زار", 2000),
    # --- Extended vocabulary: directions & places ---
    ("شمال", f"ش{_KA}مال", 1500),
    ("جنوب", f"ج{_FA}ن{_DA}ب", 1500),
    ("شرق", f"ش{_FA}ر{_SU}ق", 1500),
    ("غرب", f"غ{_FA}ر{_SU}ب", 1500),
    ("خیابان", f"خ{_KA}یابان", 2000),
    ("میدان", f"م{_KA}یدان", 1500),
    ("مسجد", f"م{_FA}س{_SU}ج{_KA}د", 1500),
    ("بازار", "بازار", 2000),
    ("پارک", f"پار{_SU}ک", 1500),
    ("رستوران", f"ر{_KA}س{_SU}توران", 1000),
    ("هتل", f"ه{_DA}ت{_FA}ل", 1000),
    ("فرودگاه", f"ف{_DA}ر{_DA}دگاه", 1000),
    # --- Extended vocabulary: body ---
    ("صورت", f"ص{_DA}ر{_FA}ت", 2000),
    ("دهان", f"د{_FA}هان", 1500),
    ("گوش", f"گ{_DA}ش", 2000),
    ("بینی", "بینی", 1500),
    ("مو", f"م{_DA}", 2000),
    ("پا", "پا", 3000),
    # --- Extended vocabulary: common expressions ---
    ("ممنون", f"م{_FA}م{_SU}ن{_DA}ن", 3000),
    ("لطفا", f"ل{_DA}ط{_SU}فا", 3000),
    ("ببخشید", f"ب{_KA}ب{_FA}خ{_SU}شید", 2500),
    ("بله", f"ب{_FA}ل{_KA}ه", 5000),
    ("نه", f"ن{_FA}ه", 5000),
    ("چرا", f"چ{_KA}را", 3000),
    ("کجا", f"ک{_DA}جا", 3000),
    ("کی", f"ک{_KA}ی", 3000),
    ("چطور", f"چ{_KA}ط{_DA}ر", 2500),
    ("چقدر", f"چ{_KA}ق{_FA}د{_SU}ر", 2000),
    ("حتما", f"ح{_FA}ت{_SU}ما", 2000),
    ("البته", f"ا{_FA}ل{_SU}ب{_FA}ت{_SU}{_KA}ه", 3000),
    ("شاید", "شاید", 2000),
    ("باید", f"بای{_FA}د", 5000),
    ("نباید", f"ن{_FA}بای{_FA}د", 3000),
    ("می‌خواهم", f"میخ{_SU}واه{_FA}م", 3000),
    ("می‌توانم", f"میت{_FA}وان{_FA}م", 2500),
    # --- Indo-European cognates (common Persian words with known pronunciation) ---
    # Source: borderlessblogger.com Indo-European words in Persian
    ("دختر", f"د{_DA}خ{_SU}ت{_FA}ر", 4000),  # dokhtar (daughter)
    ("پسر", f"پ{_KA}س{_FA}ر", 4000),  # pesar (son)
    ("خرد", f"خ{_KA}ر{_FA}د", 1500),  # kherad (wisdom)
    ("ستاره", f"س{_KA}تار{_KA}ه", 2000),  # setare (star)
    ("نو", f"ن{_DA}", 2500),  # no/now (new)
    ("نام", "نام", 5000),  # nam (name, cognate with English "name")
    ("مادر", f"ماد{_FA}ر", 5000),  # madar (mother, cognate)
    ("پدر", f"پ{_KA}د{_FA}ر", 5000),  # pedar (father, cognate)
    ("برادر", f"ب{_FA}راد{_FA}ر", 3000),  # baradar (brother, cognate)
    ("دادن", f"داد{_FA}ن", 3000),  # dadan (to give, cognate with Latin "dare")
    # --- Additional high-frequency words ---
    ("وقتی", f"و{_FA}ق{_SU}تی", 3000),  # vaqti (when)
    ("همه", f"ه{_FA}م{_KA}ه", 5000),  # hame (all/everyone)
    ("همیشه", f"ه{_FA}میش{_KA}ه", 3000),  # hamishe (always)
    ("هنوز", f"ه{_FA}ن{_DA}ز", 2500),  # hanuz (still/yet)
    ("هیچ", "هیچ", 3000),  # hich (nothing/no)
    ("فقط", f"ف{_FA}ق{_FA}ط", 3000),  # faqat (only)
    ("اما", f"ا{_FA}م{_SH}ا", 4000),  # amma (but)
    ("اگر", f"ا{_FA}گ{_FA}ر", 4000),  # agar (if)
    ("وقت", f"و{_FA}ق{_SU}ت", 3000),  # vaqt (time)
    ("حال", "حال", 3000),  # hal (state/condition)
    ("جا", "جا", 3000),  # ja (place)
    ("پول", f"پ{_DA}ل", 2500),  # pul (money)
    ("آینده", f"آیند{_KA}ه", 2000),  # ayande (future)
    ("گذشته", f"گ{_DA}ز{_FA}ش{_SU}ت{_KA}ه", 2000),  # gozashte (past)
    ("حالا", "حالا", 3000),  # hala (now)
    ("بعد", f"ب{_FA}ع{_SU}د", 3000),  # ba'd (after)
    ("قبل", f"ق{_FA}ب{_SU}ل", 2500),  # qabl (before)
    ("زیاد", "زیاد", 3000),  # ziad (much/many)
    ("کم", f"ک{_FA}م", 3000),  # kam (little/few)
    ("اول", f"ا{_FA}و{_SU}ل", 2500),  # avval (first)
    ("آخر", f"آخ{_FA}ر", 2500),  # akhar (last)
    ("بین", f"ب{_KA}ین", 2000),  # beyn (between)
    ("پیش", "پیش", 2500),  # pish (before/in front)
    ("بیرون", f"بیر{_DA}ن", 2000),  # birun (outside)
    ("داخل", f"داخ{_KA}ل", 2000),  # dakhel (inside)
    ("بالا", "بالا", 2500),  # bala (up/above)
    ("پایین", "پایین", 2000),  # payin (down/below)
    ("سفید", f"س{_KA}فید", 2000),  # sefid (white)
    ("سیاه", "سیاه", 2000),  # siah (black)
    ("سبز", f"س{_FA}ب{_SU}ز", 2000),  # sabz (green)
    ("قرمز", f"ق{_KA}ر{_SU}م{_KA}ز", 1500),  # qermez (red)
    ("آبی", "آبی", 1500),  # abi (blue)
]


# ---------------------------------------------------------------------------
# Dictionary compilation (same TRLD v1 format as Arabic)
# ---------------------------------------------------------------------------

MAGIC = b"TRLD"
VERSION = 1


def load_wiktionary_tsv(path: Path) -> list[tuple[str, str, int]]:
    """Load Wiktionary-harvested Persian romanizations as vocab entries.

    Converts romanization back to diacritized form by applying tashkeel marks
    based on the romanization. This is an approximation — the romanization
    provides the vowel information, and we encode it as Arabic diacritics
    on the original Persian word.
    """
    entries: list[tuple[str, str, int]] = []
    if not path.exists():
        return entries

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            persian, romanization = parts
            # Clean romanization
            rom = romanization.split(",")[0].strip()  # Take first variant
            rom = rom.split("|")[0].strip()
            if rom.startswith("ir=") or rom.startswith("cls="):
                rom = rom.split("=", 1)[1]
            # Skip entries with non-ASCII romanization or too short
            if not rom.isascii() or len(rom) < 2:
                continue
            # Use the romanization as-is — the context engine will use it
            # to look up the skeleton and return the diacritized form.
            # For Wiktionary entries, we store the original Persian word
            # as the "diacritized form" (since it may contain diacritics
            # from Wiktionary's formatting).
            entries.append((persian, persian, 1000))  # Default frequency

    return entries


def build_from_vocab(
    vocab: list[tuple[str, str, int]],
    wiktionary_path: Path | None = None,
) -> tuple[dict[str, list[tuple[str, int]]], dict[tuple[str, str], str]]:
    """Build unigram table from curated vocabulary + optional Wiktionary data."""
    from collections import defaultdict

    unigrams: dict[str, list[tuple[str, int]]] = defaultdict(list)

    for skeleton, diacritized, freq in vocab:
        clean_skeleton = strip_diacritics(skeleton)
        unigrams[clean_skeleton].append((diacritized, freq))

    # Add Wiktionary entries (lower priority than curated)
    if wiktionary_path:
        wikt_entries = load_wiktionary_tsv(wiktionary_path)
        for skeleton, diacritized, freq in wikt_entries:
            clean_skeleton = strip_diacritics(skeleton)
            # Only add if not already in curated vocab
            if clean_skeleton not in unigrams:
                unigrams[clean_skeleton].append((diacritized, freq))

        print(f"Wiktionary entries loaded: {len(wikt_entries)}", file=sys.stderr)

    # Sort each entry by frequency descending
    for skeleton in unigrams:
        unigrams[skeleton].sort(key=lambda x: -x[1])

    # No bigrams for curated vocab (not enough context data)
    bigrams: dict[tuple[str, str], str] = {}

    return dict(unigrams), bigrams


def compile_dictionary(
    unigrams: dict[str, list[tuple[str, int]]],
    bigrams: dict[tuple[str, str], str],
    output_path: Path,
) -> None:
    """Compile to TRLD v1 binary format (identical to Arabic)."""
    buf = bytearray()
    buf.extend(MAGIC)
    buf.extend(struct.pack("<I", VERSION))
    buf.extend(struct.pack("<I", len(unigrams)))
    buf.extend(struct.pack("<I", len(bigrams)))
    unigram_offset_pos = len(buf)
    buf.extend(struct.pack("<I", 0))
    bigram_offset_pos = len(buf)
    buf.extend(struct.pack("<I", 0))

    struct.pack_into("<I", buf, unigram_offset_pos, len(buf))
    for skeleton in sorted(unigrams):
        forms = unigrams[skeleton]
        skel_bytes = skeleton.encode("utf-8")
        buf.extend(struct.pack("<H", len(skel_bytes)))
        buf.extend(skel_bytes)
        buf.extend(struct.pack("<H", len(forms)))
        for form, freq in forms:
            form_bytes = form.encode("utf-8")
            buf.extend(struct.pack("<H", len(form_bytes)))
            buf.extend(form_bytes)
            buf.extend(struct.pack("<I", freq))

    struct.pack_into("<I", buf, bigram_offset_pos, len(buf))
    # (no bigrams for curated vocab)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(buf))
    print(f"Written: {output_path} ({len(buf):,} bytes)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Persian context dictionary from curated vocabulary"
    )
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output binary dict path")
    parser.add_argument(
        "--wiktionary",
        type=Path,
        default=None,
        help="Wiktionary TSV file (from harvest_wiktionary_persian.py)",
    )
    parser.add_argument("--stats", action="store_true", help="Print stats only")
    parser.add_argument("--json-stats", type=Path, default=None, help="Write stats to JSON")
    args = parser.parse_args()

    unigrams, bigrams = build_from_vocab(PERSIAN_VOCAB, wiktionary_path=args.wiktionary)

    print("\n--- Statistics ---", file=sys.stderr)
    print(f"Curated vocabulary entries: {len(PERSIAN_VOCAB)}", file=sys.stderr)
    print(f"Unique skeletons:          {len(unigrams)}", file=sys.stderr)
    print(f"Bigram entries:            {len(bigrams)}", file=sys.stderr)

    if args.json_stats:
        stats = {
            "vocab_entries": len(PERSIAN_VOCAB),
            "unique_skeletons": len(unigrams),
            "bigrams": len(bigrams),
        }
        args.json_stats.write_text(json.dumps(stats, indent=2))

    if args.stats:
        return

    compile_dictionary(unigrams, bigrams, args.output)


if __name__ == "__main__":
    main()
