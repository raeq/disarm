// Java reproductions (README: J1, J2, B2).  See run.sh for the build line.
import dev.disarm.Disarm;
import dev.disarm.TargetScript;
import dev.disarm.TransliterateOptions;
import java.util.Arrays;
import java.util.function.Supplier;

public final class JavaRepro {
    static String esc(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c >= 0x20 && c < 0x7F) b.append(c);
            else b.append(String.format("\\u%04x", (int) c));
        }
        return b.append('"').toString();
    }

    static void show(String label, Supplier<Object> f) {
        String r;
        try {
            Object v = f.get();
            r = v instanceof String s ? esc(s) : String.valueOf(v);
        } catch (RuntimeException e) {
            r = "threw " + e.getClass().getSimpleName() + ": " + e.getMessage();
        }
        System.out.printf("%-52s %s%n", label, r);
    }

    public static void main(String[] args) {
        System.out.println("-- J1: lone surrogates (contract: each becomes one U+FFFD) --");
        String lone = "a" + (char) 0xD800 + "b";
        show("transliterate(\"a\\ud800b\")", () -> Disarm.transliterate(lone));
        show("foldCase(\"a\\ud800b\")", () -> Disarm.foldCase(lone));
        show("stripBidi(\"a\\ud800b\")", () -> Disarm.stripBidi(lone));
        show("graphemeLen(\"a\\ud800b\")", () -> Disarm.graphemeLen(lone));
        show("isSuspiciousHostname(\"a\\udc00b.com\")", () -> Disarm.isSuspiciousHostname("a" + (char) 0xDC00 + "b.com"));
        String pair = "x" + (char) 0xD83D + (char) 0xDE00 + "y"; // a well-formed pair
        show("replaceEmoji(\"x\\ud83d\\ude00y\", \"\")", () -> Disarm.replaceEmoji(pair, ""));
        // One lone surrogate anywhere makes the whole string fall back to a lossy decode of
        // its modified-UTF-8 bytes, so a well-formed emoji beside it is destroyed too.
        show("replaceEmoji(\"x\\ud83d\\ude00y\\ud800\", \"\")", () -> Disarm.replaceEmoji(pair + (char) 0xD800, ""));
        show("demojize(\"\\ud83d\\ude00 \\ud800\")", () -> Disarm.demojize("" + (char) 0xD83D + (char) 0xDE00 + " " + (char) 0xD800));

        System.out.println("-- B2: an unknown `lang` is accepted silently --");
        String kyiv = "\u041a\u0438\u0457\u0432";
        show("transliterate(kyiv, lang(\"uk\"))",
                () -> Disarm.transliterate(kyiv, TransliterateOptions.builder().lang("uk").build()));
        show("transliterate(kyiv, lang(\"UK\"))",
                () -> Disarm.transliterate(kyiv, TransliterateOptions.builder().lang("UK").build()));
        show("searchKey(kyiv, \"UK\")", () -> Disarm.searchKey(kyiv, "UK"));

        System.out.println("-- J2: confusable targets the core accepts but the JVM surface cannot name --");
        show("Arrays.toString(TargetScript.values())", () -> Arrays.toString(TargetScript.values()));
        show("TargetScript.valueOf(\"ARABIC\")", () -> TargetScript.valueOf("ARABIC"));
    }
}
