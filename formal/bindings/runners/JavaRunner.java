// Harness runner for the Java binding: the public facade dev.disarm.Disarm.
// Protocol: see ../rust_oracle/src/main.rs and ../README.md ("The harness").
//
// Build: javac -cp <disarm-java classes> -d <out> JavaRunner.java
// Run:   java -Ddisarm.native.lib=<libdisarm_jni.so> -cp <classes>:<out> JavaRunner crc CORPUS CASES

import dev.disarm.AnomalyReport;
import dev.disarm.AutoLangInspection;
import dev.disarm.DigitPolicy;
import dev.disarm.Disarm;
import dev.disarm.DisarmException;
import dev.disarm.DisarmInvalidArgumentException;
import dev.disarm.Finding;
import dev.disarm.HostnameAnalysis;
import dev.disarm.MlNormalizeOptions;
import dev.disarm.NormalizationForm;
import dev.disarm.TargetScript;
import dev.disarm.TransliterateOptions;
import java.io.BufferedWriter;
import java.io.ByteArrayOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.zip.CRC32;

public final class JavaRunner {
    static final int NSCALAR = 0x110000 - 0x800;
    static final int BLOCK = 4096;

    record Rec(Object... fields) {}

    static void enc(Object v, ByteArrayOutputStream out) {
        if (v instanceof Boolean b) {
            out.writeBytes(b ? "b1".getBytes() : "b0".getBytes());
        } else if (v instanceof Number n) {
            out.writeBytes(("i" + n.longValue() + ";").getBytes());
        } else if (v == null) {
            out.write('n');
        } else if (v instanceof String s) {
            // A lone surrogate has no UTF-8 form; encode it visibly rather than as '?'.
            byte[] b = s.codePoints().anyMatch(c -> c >= 0xD800 && c <= 0xDFFF)
                    ? ("<lone surrogate in output>" + s.replaceAll("[\\uD800-\\uDFFF]", "?")).getBytes(StandardCharsets.UTF_8)
                    : s.getBytes(StandardCharsets.UTF_8);
            out.writeBytes(("s" + b.length + ":").getBytes());
            out.writeBytes(b);
        } else if (v instanceof Rec r) {
            out.writeBytes(("r" + r.fields().length + ":").getBytes());
            for (Object f : r.fields()) enc(f, out);
        } else if (v instanceof List<?> l) {
            out.writeBytes(("l" + l.size() + ":").getBytes());
            for (Object x : l) enc(x, out);
        } else {
            throw new IllegalArgumentException("cannot encode " + v.getClass());
        }
    }

    static byte[] encodeCall(Function<String, Object> fn, String t) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        Object v;
        try {
            v = fn.apply(t);
        } catch (DisarmInvalidArgumentException e) {
            out.writeBytes("einv:".getBytes());
            enc(e.getMessage(), out);
            return out.toByteArray();
        } catch (DisarmException e) {
            out.writeBytes("eerr:".getBytes());
            enc(e.getMessage(), out);
            return out.toByteArray();
        } catch (RuntimeException e) {
            out.writeBytes(("ejava:" + e.getClass().getName() + ":").getBytes());
            enc(String.valueOf(e.getMessage()), out);
            return out.toByteArray();
        }
        enc(v, out);
        return out.toByteArray();
    }

    static Rec host(HostnameAnalysis a) {
        return new Rec(a.suspicious(), a.scripts(), a.mixedScript(), a.hasConfusables(), a.bidiConflict(),
                a.bidiControl(), a.hasInvisible(), a.compatFold(), a.crossLabelScript(), a.labelScripts(),
                a.wholeScriptConfusable(), a.labelWholeScriptConfusable(), a.canonical());
    }

    static Rec anomalies(AnomalyReport r) {
        List<Object> fs = new ArrayList<>();
        for (Finding f : r.findings()) {
            fs.add(new Rec(f.kind(), f.token(), f.start(), f.end(), f.detail(), f.reason()));
        }
        return new Rec(r.anomalous(), r.kinds(), fs, r.reason());
    }

    static TransliterateOptions lang(String l) {
        return TransliterateOptions.builder().lang(l).build();
    }

    static TransliterateOptions scheme(TransliterateOptions.Scheme s) {
        return TransliterateOptions.builder().scheme(s).build();
    }

    static final Map<String, Function<String, Object>> CASES = new LinkedHashMap<>();

    static {
        var C = CASES;
        C.put("tr", t -> Disarm.transliterate(t));
        C.put("tr_iso9", t -> Disarm.transliterate(t, scheme(TransliterateOptions.Scheme.STRICT_ISO9)));
        C.put("tr_gost", t -> Disarm.transliterate(t, scheme(TransliterateOptions.Scheme.GOST7034)));
        C.put("tr_de", t -> Disarm.transliterate(t, lang("de")));
        C.put("tr_auto", t -> Disarm.transliterate(t, lang("auto")));
        C.put("tr_uk", t -> Disarm.transliterate(t, lang("uk")));
        C.put("tr_ja", t -> Disarm.transliterate(t, lang("ja")));
        C.put("tr_bad", t -> Disarm.transliterate(t, lang("xx")));
        C.put("nc_lat", t -> Disarm.normalizeConfusables(t, TargetScript.LATIN));
        C.put("nc_lat_tr39", t -> Disarm.normalizeConfusables(t, TargetScript.LATIN, DigitPolicy.TR39));
        C.put("nc_lat_pres", t -> Disarm.normalizeConfusables(t, TargetScript.LATIN, DigitPolicy.PRESERVE));
        C.put("nc_cyr", t -> Disarm.normalizeConfusables(t, TargetScript.CYRILLIC));
        // nc_ara / nc_heb: TargetScript has no ARABIC or HEBREW constant; not expressible.
        C.put("sa", t -> Disarm.stripAccents(t));
        C.put("fc", t -> Disarm.foldCase(t));
        C.put("cfs", t -> Disarm.isCaseFoldStable(t));
        C.put("dj", t -> Disarm.demojize(t));
        C.put("dj_sm", t -> Disarm.demojize(t, true));
        C.put("re_empty", t -> Disarm.replaceEmoji(t, ""));
        C.put("re_sp", t -> Disarm.replaceEmoji(t, " "));
        C.put("cw", t -> Disarm.collapseWhitespace(t));
        C.put("scc", t -> Disarm.stripControlChars(t));
        C.put("szw", t -> Disarm.stripZeroWidthChars(t));
        C.put("sbd", t -> Disarm.stripBidi(t));
        C.put("stg", t -> Disarm.stripTags(t));
        C.put("svs", t -> Disarm.stripVariationSelectors(t));
        C.put("snc", t -> Disarm.stripNoncharacters(t));
        C.put("spua", t -> Disarm.stripPua(t));
        C.put("can", t -> Disarm.canonicalize(t));
        C.put("can_tr39", t -> Disarm.canonicalize(t, DigitPolicy.TR39));
        C.put("can_pres", t -> Disarm.canonicalize(t, DigitPolicy.PRESERVE));
        C.put("cans", t -> Disarm.canonicalizeStrict(t));
        C.put("sfmt", t -> Disarm.stripFormat(t));
        C.put("sobf", t -> Disarm.stripObfuscation(t));
        C.put("sobf_tr39", t -> Disarm.stripObfuscation(t, DigitPolicy.TR39));
        C.put("sk", t -> Disarm.searchKey(t));
        C.put("sk_de", t -> Disarm.searchKey(t, "de"));
        C.put("sok", t -> Disarm.sortKey(t));
        C.put("ck", t -> Disarm.catalogKey(t));
        C.put("ck_iso", t -> Disarm.catalogKey(t, null, true));
        C.put("skel", t -> Disarm.skeletonKey(t));
        C.put("skel_tr39", t -> Disarm.skeletonKey(t, DigitPolicy.TR39));
        C.put("nfc", t -> Disarm.normalize(t, NormalizationForm.NFC));
        C.put("nfd", t -> Disarm.normalize(t, NormalizationForm.NFD));
        C.put("nfkc", t -> Disarm.normalize(t, NormalizationForm.NFKC));
        C.put("nfkd", t -> Disarm.normalize(t, NormalizationForm.NFKD));
        C.put("isn_nfc", t -> Disarm.isNormalized(t, NormalizationForm.NFC));
        C.put("mix", t -> Disarm.isMixedScript(t));
        C.put("bconf", t -> Disarm.hasBidiConflict(t));
        C.put("bctl", t -> Disarm.hasBidiControl(t));
        C.put("susp", t -> Disarm.isSuspiciousHostname(t));
        C.put("ah", t -> host(Disarm.analyzeHostname(t)));
        C.put("ah_c", t -> host(Disarm.analyzeHostname(t, true)));
        C.put("glen", t -> Disarm.graphemeLen(t));
        C.put("gsplit", t -> Disarm.graphemeSplit(t));
        C.put("gtrunc1", t -> Disarm.graphemeTruncate(t, 1));
        C.put("tw", t -> Disarm.terminalWidth(t));
        C.put("tw_amb", t -> Disarm.terminalWidth(t, true));
        C.put("ial", t -> {
            AutoLangInspection a = Disarm.inspectAutoLang(t);
            return new Rec(a.script(), a.chosenLang(), a.reason(), a.discriminatorsHit());
        });
        C.put("ds", t -> Disarm.detectScripts(t));
        C.put("iscan", t -> Disarm.isCanonical(t));
        C.put("mln", t -> Disarm.mlNormalize(t));
        C.put("mln_nofold", t -> Disarm.mlNormalize(t, MlNormalizeOptions.builder().foldCase(false).build()));
        C.put("sfn", t -> Disarm.sanitizeFilename(t));
        C.put("ia", t -> anomalies(Disarm.inspectAnomalies(t, List.of())));
        C.put("ha", t -> Disarm.hasAnomalies(t, List.<String>of()));
        C.put("ed", t -> Disarm.editDistance(t, "paypal"));
        C.put("fu", t -> Disarm.findUntranslatable(t).stream().map(u -> (Object) new Rec(u.character(), u.offset())).toList());
        C.put("fuc", t -> Disarm.findUnmappedConfusables(t).stream().map(u -> (Object) new Rec(u.character(), u.offset())).toList());
        C.put("rv_ru", t -> Disarm.reverseTransliterate(t, "ru"));
        C.put("rv_el", t -> Disarm.reverseTransliterate(t, "el"));
        C.put("rv_uk", t -> Disarm.reverseTransliterate(t, "uk"));
        C.put("slug", t -> Disarm.slugify(t));
        C.put("zs", t -> Disarm.stripZalgo(t, 3));
        C.put("zi", t -> Disarm.isZalgo(t, 3));
        C.put("isconf", t -> Disarm.isConfusable(t, TargetScript.LATIN));
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        var out = new BufferedWriter(new OutputStreamWriter(System.out, StandardCharsets.US_ASCII), 1 << 16);
        if (mode.equals("list")) {
            out.write(String.join(",", CASES.keySet()) + "\n");
            out.flush();
            return;
        }
        List<String> corpus = new ArrayList<>();
        HexFormat hex = HexFormat.of();
        for (String line : Files.readAllLines(Path.of(args[1]), StandardCharsets.US_ASCII)) {
            corpus.add(new String(hex.parseHex(line), StandardCharsets.UTF_8));
        }
        int total = NSCALAR + corpus.size();
        Function<Integer, String> inp = i -> i < NSCALAR
                ? new String(Character.toChars(i < 0xD800 ? i : i + 0x800))
                : corpus.get(i - NSCALAR);
        if (mode.equals("crc")) {
            for (String c : args[2].split(",")) {
                var fn = CASES.get(c);
                if (fn == null) continue;
                for (int b = 0; (long) b * BLOCK < total; b++) {
                    int lo = b * BLOCK, hi = Math.min(lo + BLOCK, total);
                    CRC32 crc = new CRC32();
                    for (int i = lo; i < hi; i++) crc.update(encodeCall(fn, inp.apply(i)));
                    out.write(String.format("%s\t%d\t%08x\t%d%n", c, b, crc.getValue(), hi - lo));
                }
            }
        } else if (mode.equals("dump")) {
            var fn = CASES.get(args[2]);
            int hi = Math.min(Integer.parseInt(args[4]), total);
            for (int i = Integer.parseInt(args[3]); i < hi; i++) {
                out.write(i + "\t" + hex.formatHex(encodeCall(fn, inp.apply(i))) + "\n");
            }
        } else {
            throw new IllegalArgumentException("unknown mode " + mode);
        }
        out.flush();
    }
}
