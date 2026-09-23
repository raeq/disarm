/*
 * The documented C ABI contract, exercised end to end on the real library.
 *
 * Calls every exported function on success and error paths, checks the
 * DisarmResult rule ("exactly one of value / error is non-NULL"), checks that
 * every returned string is valid UTF-8, and frees every returned pointer
 * (both halves of every DisarmResult, NULL included) with disarm_string_free.
 * Run under AddressSanitizer + LeakSanitizer and under valgrind (see run.sh):
 * a leak, double free or invalid access on any path fails the run.
 *
 * Non-ASCII test data is written as byte escapes only.
 */
#include "disarm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures = 0;
static int calls = 0;

static int valid_utf8(const unsigned char *s) {
    while (*s) {
        unsigned c = *s;
        int n = c < 0x80 ? 0 : (c >> 5) == 6 ? 1 : (c >> 4) == 14 ? 2 : (c >> 3) == 30 ? 3 : -1;
        if (n < 0) return 0;
        unsigned cp = n == 0 ? c : n == 1 ? (c & 0x1F) : n == 2 ? (c & 0x0F) : (c & 0x07);
        for (int i = 1; i <= n; i++) {
            if ((s[i] & 0xC0) != 0x80) return 0;
            cp = (cp << 6) | (s[i] & 0x3F);
        }
        if ((n == 1 && cp < 0x80) || (n == 2 && cp < 0x800) || (n == 3 && cp < 0x10000) ||
            cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF))
            return 0;
        s += n + 1;
    }
    return 1;
}

static void str_(const char *label, char *s) {
    calls++;
    if (!s) { printf("FAIL %s: NULL char*\n", label); failures++; return; }
    if (!valid_utf8((const unsigned char *)s)) { printf("FAIL %s: output not UTF-8\n", label); failures++; }
#ifdef SELFTEST_LEAK
    /* Harness validation: skip one free; ASan/LSan and valgrind must report it. */
    if (!strcmp(label, "fold_case")) return;
#endif
    disarm_string_free(s);
}

/* want: 1 = expect success, 0 = expect error, -1 = either */
static void res_(const char *label, DisarmResult_t r, int want) {
    calls++;
    if ((r.value == NULL) == (r.error == NULL)) {
        printf("FAIL %s: value=%p error=%p (exactly one must be set)\n", label, (void *)r.value, (void *)r.error);
        failures++;
    }
    if (want == 1 && !r.value) { printf("FAIL %s: unexpected error: %s\n", label, r.error ? r.error : "?"); failures++; }
    if (want == 0 && !r.error) { printf("FAIL %s: expected an error\n", label); failures++; }
    if (r.value && !valid_utf8((const unsigned char *)r.value)) { printf("FAIL %s: value not UTF-8\n", label); failures++; }
    if (r.error && !valid_utf8((const unsigned char *)r.error)) { printf("FAIL %s: error not UTF-8\n", label); failures++; }
    /* The header: free whichever is set; NULL is a no-op, so free both. */
    disarm_string_free(r.value);
    disarm_string_free(r.error);
}

static const char *const TEXTS[] = {
    "",
    "plain ascii",
    "Caf\xC3\xA9 \xE2\x80\xAE" "evil\xE2\x80\xAC.exe",
    "\xD0\x9C\xD0\xBE\xD1\x81\xD0\xBA\xD0\xB2\xD0\xB0",           /* Cyrillic word */
    "\xD0\xB0pple.com",                                              /* Cyrillic a + pple */
    "\xF0\x9F\x91\x8D\xF0\x9F\x8F\xBD x\xE2\x80\x8By",              /* emoji + ZWSP */
    "a\xCC\x81\xCC\x82\xCC\x83\xCC\x84\xCC\x85",                    /* zalgo */
    "\xE0\xA5\xA8\xE0\xA5\xA6\xE0\xA5\xA8\xE0\xA5\xA6",             /* Devanagari digits */
    "\xF3\xA0\x80\x81\xF3\xA0\x81\xA1",                              /* tag characters */
};

int main(void) {
    size_t nt = sizeof TEXTS / sizeof *TEXTS;
    for (size_t i = 0; i < nt; i++) {
        const char *t = TEXTS[i];
        str_("transliterate", disarm_transliterate(t));
        res_("transliterate_opts", disarm_transliterate_opts(t, "default", NULL), 1);
        res_("transliterate_opts iso9 uk", disarm_transliterate_opts(t, "strict_iso9", "uk"), 1);
        res_("transliterate_opts bad scheme", disarm_transliterate_opts(t, "nope", NULL), 0);
        res_("reverse_transliterate", disarm_reverse_transliterate(t, "ru"), 1);
        res_("reverse_transliterate bad", disarm_reverse_transliterate(t, "zz"), 0);
        res_("normalize_confusables", disarm_normalize_confusables(t, "latin"), 1);
        res_("normalize_confusables bad", disarm_normalize_confusables(t, "klingon"), 0);
        res_("normalize_confusables_opts", disarm_normalize_confusables_opts(t, "hebrew", "preserve"), 1);
        res_("normalize_confusables_opts bad", disarm_normalize_confusables_opts(t, "latin", "roman"), 0);
        res_("normalize", disarm_normalize(t, "NFKD"), 1);
        res_("normalize bad", disarm_normalize(t, "NFX"), 0);
        str_("strip_accents", disarm_strip_accents(t));
        str_("fold_case", disarm_fold_case(t));
        (void)disarm_is_case_fold_stable(t);
        str_("demojize", disarm_demojize(t, true));
        str_("replace_emoji", disarm_replace_emoji(t, ""));
        str_("collapse_whitespace", disarm_collapse_whitespace(t));
        str_("strip_control_chars", disarm_strip_control_chars(t));
        str_("strip_zero_width_chars", disarm_strip_zero_width_chars(t));
        str_("strip_bidi", disarm_strip_bidi(t));
        str_("strip_tags", disarm_strip_tags(t));
        str_("strip_variation_selectors", disarm_strip_variation_selectors(t));
        str_("strip_noncharacters", disarm_strip_noncharacters(t));
        str_("strip_pua", disarm_strip_pua(t));
        str_("strip_format", disarm_strip_format(t));
        res_("canonicalize", disarm_canonicalize(t), 1);
        res_("canonicalize_opts", disarm_canonicalize_opts(t, "tr39"), 1);
        res_("canonicalize_opts bad", disarm_canonicalize_opts(t, "x"), 0);
        res_("canonicalize_strict", disarm_canonicalize_strict(t), -1);
        res_("canonicalize_strict_opts bad", disarm_canonicalize_strict_opts(t, "x"), 0);
        res_("strip_obfuscation", disarm_strip_obfuscation(t), 1);
        res_("strip_obfuscation_opts bad", disarm_strip_obfuscation_opts(t, "x"), 0);
        res_("search_key", disarm_search_key(t, NULL), 1);
        res_("search_key_opts", disarm_search_key_opts(t, "de", "preserve"), 1);
        res_("search_key_opts bad", disarm_search_key_opts(t, NULL, "x"), 0);
        res_("sort_key", disarm_sort_key(t, NULL), 1);
        res_("sort_key_opts bad", disarm_sort_key_opts(t, NULL, "x"), 0);
        res_("catalog_key", disarm_catalog_key(t, NULL, true), 1);
        res_("catalog_key_opts bad", disarm_catalog_key_opts(t, NULL, false, "x"), 0);
        res_("skeleton_key", disarm_skeleton_key(t, "tr39"), 1);
        res_("skeleton_key bad", disarm_skeleton_key(t, "x"), 0);
        (void)disarm_edit_distance(t, "paypal");
        res_("nearest_match", disarm_nearest_match(t, "[\"paypal\",\"apple\"]", 3), 1);
        res_("nearest_match bad json", disarm_nearest_match(t, "{", 3), 0);
        (void)disarm_is_canonical(t, "canonicalize");
        (void)disarm_is_canonical(t, "no-such-preset");
        (void)disarm_is_suspicious_hostname(t);
        (void)disarm_is_mixed_script(t);
        (void)disarm_has_bidi_conflict(t);
        (void)disarm_has_bidi_control(t);
        (void)disarm_grapheme_len(t);
        (void)disarm_terminal_width(t, true);
        str_("analyze_hostname", disarm_analyze_hostname(t));
        str_("analyze_hostname_opts", disarm_analyze_hostname_opts(t, true));
        str_("inspect_anomalies", disarm_inspect_anomalies(t, "[\"free\"]"));
        str_("inspect_anomalies bad json", disarm_inspect_anomalies(t, "not json"));
        res_("find_key_collisions", disarm_find_key_collisions("[\"A\",\"a\"]", "fold_case", NULL), 1);
        res_("find_key_collisions bad key", disarm_find_key_collisions("[]", "x", NULL), 0);
        res_("find_key_collisions bad json", disarm_find_key_collisions("[", "fold_case", NULL), 0);
        str_("inspect_auto_lang", disarm_inspect_auto_lang(t));
        res_("ml_normalize", disarm_ml_normalize(t, NULL, "cldr", false), 1);
        res_("ml_normalize bad", disarm_ml_normalize(t, NULL, "x", true), 0);
        res_("sanitize_filename", disarm_sanitize_filename(t, "_", 255, "windows", NULL, true), 1);
        res_("sanitize_filename bad", disarm_sanitize_filename(t, "_", 255, "amiga", NULL, true), 0);
        res_("find_unmapped_confusables", disarm_find_unmapped_confusables(t, "latin"), 1);
        res_("find_unmapped_confusables bad", disarm_find_unmapped_confusables(t, "x"), 0);
    }
    res_("lang_info", disarm_lang_info("de"), 1);
    res_("lang_info bad", disarm_lang_info("xx"), 0);
    res_("script_info", disarm_script_info("Cyrillic"), 1);
    res_("script_info bad", disarm_script_info("Klingon"), 0);
    res_("confusable_coverage", disarm_confusable_coverage("Cyrillic"), 1);
    res_("confusable_coverage bad", disarm_confusable_coverage("Klingon"), 0);
    res_("unmapped_confusables", disarm_unmapped_confusables("latin"), 1);
    res_("unmapped_confusables bad", disarm_unmapped_confusables("x"), 0);
    str_("confusables_version", disarm_confusables_version());
    str_("unicode_version", disarm_unicode_version());
    (void)disarm_key_schema_version();
    disarm_string_free(NULL); /* documented no-op */
    printf("%d string-returning calls, %d failures\n", calls, failures);
    return failures != 0;
}
