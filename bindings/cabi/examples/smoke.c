/*
 * Smoke test for the disarm C ABI: links the library, exercises a plain string
 * return, a fallible DisarmResult (success + error paths), and frees every
 * returned string. Proves the header + ABI + ownership contract end-to-end.
 *
 * Build & run (from bindings/cabi, after `cargo build --release` and header gen):
 *   cc examples/smoke.c target/release/libdisarm_ffi.a -I. -o /tmp/smoke -lSystem
 *   /tmp/smoke
 */
#include "disarm.h"
#include <stdio.h>
#include <string.h>

static int failures = 0;

static void check(const char *label, const char *got, const char *want) {
    int ok = got && strcmp(got, want) == 0;
    printf("%-28s %-6s got=\"%s\" want=\"%s\"\n", label, ok ? "OK" : "FAIL",
           got ? got : "(null)", want);
    if (!ok) failures++;
}

int main(void) {
    /* Plain string return: fullwidth H + accented e -> "Hello". */
    char *ascii = disarm_transliterate("Ｈéllo");
    check("transliterate", ascii, "Hello");
    disarm_string_free(ascii);

    /* Fallible success: NFC normalization returns a value, no error. */
    DisarmResult_t nfc = disarm_normalize("é", "NFC");
    printf("%-28s %-6s\n", "normalize NFC value!=null", nfc.value ? "OK" : "FAIL");
    if (!nfc.value) failures++;
    if (nfc.error) { printf("unexpected error: %s\n", nfc.error); failures++; }
    disarm_string_free(nfc.value);
    disarm_string_free(nfc.error);

    /* Fallible error: a bogus normalization form yields error, no value. */
    DisarmResult_t bad = disarm_normalize("x", "NOPE");
    printf("%-28s %-6s (err=%s)\n", "normalize bad-form -> error",
           (bad.error && !bad.value) ? "OK" : "FAIL", bad.error ? bad.error : "(null)");
    if (!(bad.error && !bad.value)) failures++;
    disarm_string_free(bad.value);
    disarm_string_free(bad.error);

    /* Predicate: Cyrillic spoof hostname. */
    int spoof = disarm_is_suspicious_hostname("аpple.com");
    printf("%-28s %-6s\n", "suspicious hostname", spoof ? "OK" : "FAIL");
    if (!spoof) failures++;

    /* Structured report (JSON transport, #553): whole-script spoof аррӏе -> apple. */
    char *analysis = disarm_analyze_hostname("аррӏе.com");
    int json_ok = analysis
        && strstr(analysis, "\"canonical\":\"apple.com\"")
        && strstr(analysis, "\"whole_script_confusable\":true");
    printf("%-28s %-6s\n", "analyze_hostname JSON", json_ok ? "OK" : "FAIL");
    if (!json_ok) failures++;
    disarm_string_free(analysis);

    /* Anomaly report with a lexicon (#553): leet "fr33" -> "free" needs the wordlist. */
    char *anom = disarm_inspect_anomalies("get fr33", "[\"free\"]");
    int anom_ok = anom
        && strstr(anom, "\"kind\":\"leet\"")
        && strstr(anom, "\"detail\":\"free\"");
    printf("%-28s %-6s\n", "inspect_anomalies leet", anom_ok ? "OK" : "FAIL");
    if (!anom_ok) failures++;
    disarm_string_free(anom);

    /* Empty lexicon: same leet input is NOT reported (structural-only mode). */
    char *anom0 = disarm_inspect_anomalies("get fr33", "");
    int anom0_ok = anom0 && !strstr(anom0, "\"leet\"");
    printf("%-28s %-6s\n", "inspect_anomalies no-lex", anom0_ok ? "OK" : "FAIL");
    if (!anom0_ok) failures++;
    disarm_string_free(anom0);

    /* Bundled data version (#560): a dotted numeric string, not the crate version. */
    char *cv = disarm_confusables_version();
    int cv_ok = cv && cv[0] >= '0' && cv[0] <= '9' && strchr(cv, '.') != NULL;
    printf("%-28s %-6s got=\"%s\"\n", "confusables_version", cv_ok ? "OK" : "FAIL",
           cv ? cv : "(null)");
    if (!cv_ok) failures++;
    disarm_string_free(cv);

    /* Coverage introspection (#563): a JSON array, and a scan that finds nothing on
       a homoglyph the table DOES fold. */
    DisarmResult_t unmapped = disarm_unmapped_confusables("latin");
    int unmapped_ok = unmapped.value && unmapped.value[0] == '[' && strlen(unmapped.value) > 100;
    printf("%-28s %-6s\n", "unmapped_confusables JSON", unmapped_ok ? "OK" : "FAIL");
    if (!unmapped_ok) failures++;
    disarm_string_free(unmapped.value);
    disarm_string_free(unmapped.error);

    /* Cyrillic а (U+0430, "\xd0\xb0") folds, so the scan reports an empty array. */
    DisarmResult_t scan = disarm_find_unmapped_confusables("p\xd0\xb0ypal", "latin");
    int scan_ok = scan.value && strcmp(scan.value, "[]") == 0;
    printf("%-28s %-6s got=\"%s\"\n", "find_unmapped covered", scan_ok ? "OK" : "FAIL",
           scan.value ? scan.value : "(null)");
    if (!scan_ok) failures++;
    disarm_string_free(scan.value);
    disarm_string_free(scan.error);

    /* #561 digit policy: Devanagari zeros stay numeric by default, collide under tr39. */
    DisarmResult_t dn = disarm_normalize_confusables_opts("g\xe0\xa5\xa6\xe0\xa5\xa6gle", "latin", "numeric");
    check("digit policy numeric", dn.value, "g00gle");
    disarm_string_free(dn.value);
    disarm_string_free(dn.error);

    DisarmResult_t dt = disarm_normalize_confusables_opts("g\xe0\xa5\xa6\xe0\xa5\xa6gle", "latin", "tr39");
    check("digit policy tr39", dt.value, "google");
    disarm_string_free(dt.value);
    disarm_string_free(dt.error);

    /* #586: the fold iterates to a fixed point rather than stopping after one pass.
       A fold exposes a composition: U+00A5 + U+0300 folds to Y + U+0300, which
       composes to U+1EF2. A single pass returned the decomposed "Y\u0300". */
    DisarmResult_t fp1 = disarm_normalize_confusables("\xc2\xa5\xcc\x80", "latin");
    check("fixed point: fold exposes composition", fp1.value, "\xe1\xbb\xb2");
    disarm_string_free(fp1.value);
    disarm_string_free(fp1.error);

    /* And the other direction: U+04AA + U+0327 composes to C-cedilla, itself a
       confusable, which folds to "C". A single pass returned "C\u0327", which
       disarm_is_confusable still reported as confusable. */
    DisarmResult_t fp2 = disarm_normalize_confusables("\xd2\xaa\xcc\xa7", "latin");
    check("fixed point: composition exposes fold", fp2.value, "C");
    disarm_string_free(fp2.value);
    disarm_string_free(fp2.error);

    /* ml_normalize: default folds case; fold_case=false keeps capitals, not accents. */
    DisarmResult_t mlf = disarm_ml_normalize("Jos\xc3\xa9 Mart\xc3\xadnez", NULL, "cldr", true);
    check("ml_normalize fold", mlf.value, "jose martinez");
    disarm_string_free(mlf.value);
    disarm_string_free(mlf.error);

    DisarmResult_t mlk = disarm_ml_normalize("Jos\xc3\xa9 Mart\xc3\xadnez", NULL, "cldr", false);
    check("ml_normalize keep case", mlk.value, "Jose Martinez");
    disarm_string_free(mlk.value);
    disarm_string_free(mlk.error);

    /* #562 contraction: off by default, recovers the digraph spoof when enabled. */
    char *c_off = disarm_analyze_hostname_opts("arnazon.com", false);
    int c_off_ok = c_off && strstr(c_off, "\"canonical\":\"arnazon.com\"") != NULL;
    printf("%-28s %-6s\n", "contraction off", c_off_ok ? "OK" : "FAIL");
    if (!c_off_ok) failures++;
    disarm_string_free(c_off);

    char *c_on = disarm_analyze_hostname_opts("arnazon.com", true);
    int c_on_ok = c_on && strstr(c_on, "\"canonical\":\"amazon.com\"") != NULL;
    printf("%-28s %-6s\n", "contraction on", c_on_ok ? "OK" : "FAIL");
    if (!c_on_ok) failures++;
    disarm_string_free(c_on);

    if (failures == 0) {
        printf("\nC SMOKE PASSED\n");
        return 0;
    }
    printf("\nC SMOKE FAILED: %d\n", failures);
    return 1;
}
