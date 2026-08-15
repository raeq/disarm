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

    if (failures == 0) {
        printf("\nC SMOKE PASSED\n");
        return 0;
    }
    printf("\nC SMOKE FAILED: %d\n", failures);
    return 1;
}
