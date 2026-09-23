/*
 * Reproductions for the C ABI findings (README: C1, C2, C3). Each case runs in a
 * forked child so a crash is reported instead of ending the run.
 *
 *   ./repro utf8     invalid UTF-8 input is accepted, and non-UTF-8 comes back out
 *   ./repro null     NULL for a non-nullable argument
 *   ./repro empty    an empty result is one shared, read-only pointer
 *   ./repro all
 *
 * Non-ASCII test data is written as byte escapes only.
 */
#include "disarm.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static void hex(const char *label, const char *s) {
    printf("  %-34s", label);
    if (!s) { printf("(null)\n"); return; }
    for (const unsigned char *p = (const unsigned char *)s; *p; p++) printf("%02x ", *p);
    printf("\n");
}

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

/* C1: bytes that are not UTF-8 go straight into safe Rust as &str. One child per
 * (input, function), so one crash does not hide the next result. */
static const char *const BAD[] = {
    "caf\xE9",              /* Latin-1 e-acute: a lone lead byte before the NUL */
    "\xC0\xAF" "etc",       /* overlong '/' */
    "a\xED\xA0\x80z",       /* an encoded surrogate (WTF-8 / CESU-8) */
    "ok\xE2\x82",           /* truncated 3-byte sequence at the end */
    "\xFF\xFE",
    "\xE9t\xE9",            /* Latin-1 "ete" */
};
static const char *cur;

static void show(const char *label, char *out) {
    hex(label, out);
    if (out) printf("  %-34s%s\n", "  output is UTF-8?", valid_utf8((const unsigned char *)out) ? "yes" : "NO");
    disarm_string_free(out);
}
static void f_strip_bidi(void) { show("disarm_strip_bidi ->", disarm_strip_bidi(cur)); }
static void f_fold_case(void) { show("disarm_fold_case ->", disarm_fold_case(cur)); }
static void f_transliterate(void) { show("disarm_transliterate ->", disarm_transliterate(cur)); }
static void f_collapse(void) { show("disarm_collapse_whitespace ->", disarm_collapse_whitespace(cur)); }
static void f_canonicalize(void) {
    DisarmResult_t r = disarm_canonicalize(cur);
    show("disarm_canonicalize value ->", r.value);
    show("disarm_canonicalize error ->", r.error);
}
static void f_suspicious(void) {
    printf("  %-34s%d\n", "disarm_is_suspicious_hostname ->", disarm_is_suspicious_hostname(cur));
}
static void f_edit(void) {
    printf("  %-34s%zu\n", "disarm_edit_distance(in, \"cafe\")", disarm_edit_distance(cur, "cafe"));
}

static void run(const char *name, void (*f)(void));

static void case_utf8(void) {
    void (*fs[])(void) = {f_strip_bidi, f_fold_case, f_transliterate, f_collapse, f_canonicalize,
                          f_suspicious, f_edit};
    for (size_t i = 0; i < sizeof BAD / sizeof *BAD; i++) {
        cur = BAD[i];
        printf("input %zu:\n", i);
        hex("bytes in", cur);
        for (size_t j = 0; j < sizeof fs / sizeof *fs; j++) run(NULL, fs[j]);
    }
}

/* C2: NULL where the header shows a plain `char const *`. */
static void case_null(void) {
    printf("disarm_transliterate(NULL) ...\n");
    fflush(stdout);
    char *s = disarm_transliterate(NULL);
    printf("  returned %p\n", (void *)s);
}

/* C3: every empty result is the same pointer, into read-only memory. */
static void case_empty(void) {
    char *a = disarm_strip_bidi("\xE2\x80\xAE");   /* U+202E alone -> "" */
    char *b = disarm_strip_zero_width_chars("\xE2\x80\x8B"); /* U+200B alone -> "" */
    printf("  two empty results: %p and %p (%s)\n", (void *)a, (void *)b, a == b ? "SAME pointer" : "distinct");
    printf("  a common idiom on an owned char*: s[strcspn(s, \"\\r\\n\")] = '\\0'\n");
    fflush(stdout);
    a[strcspn(a, "\r\n")] = '\0';
    printf("  store succeeded\n");
    disarm_string_free(a);
    disarm_string_free(b);
}

static void run(const char *name, void (*f)(void)) {
    if (name) printf("== %s ==\n", name);
    fflush(stdout);
    pid_t pid = fork();
    if (pid == 0) { f(); fflush(stdout); _exit(0); }
    int st = 0;
    waitpid(pid, &st, 0);
    if (WIFSIGNALED(st)) printf("  -> child killed by signal %d (%s)\n", WTERMSIG(st), strsignal(WTERMSIG(st)));
    else if (name) printf("  child exited %d\n", WEXITSTATUS(st));
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0); /* keep every line a crashing child printed */
    const char *which = argc > 1 ? argv[1] : "all";
    if (!strcmp(which, "utf8") || !strcmp(which, "all")) { printf("== C1 invalid UTF-8 ==\n"); case_utf8(); }
    if (!strcmp(which, "null") || !strcmp(which, "all")) run("C2 NULL argument", case_null);
    if (!strcmp(which, "empty") || !strcmp(which, "all")) run("C3 empty result", case_empty);
    return 0;
}
