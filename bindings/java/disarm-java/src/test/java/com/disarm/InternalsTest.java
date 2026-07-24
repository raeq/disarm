package com.disarm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;

import java.lang.reflect.Constructor;
import org.junit.jupiter.api.Test;

/** Covers the exception hierarchy, options builder, enum tokens, and static-holder ctors. */
class InternalsTest {

    @Test
    void exceptionHierarchyAndConstructors() {
        DisarmException e1 = new DisarmException("boom");
        assertEquals("boom", e1.getMessage());

        Throwable cause = new IllegalStateException("why");
        DisarmException e2 = new DisarmException("wrap", cause);
        assertSame(cause, e2.getCause());

        DisarmInvalidArgumentException e3 = new DisarmInvalidArgumentException("bad");
        assertInstanceOf(DisarmException.class, e3);
    }

    @Test
    void transliterateOptionsBuilder() {
        TransliterateOptions def = TransliterateOptions.builder().build();
        assertEquals("default", def.scheme());
        assertNull(def.lang());

        TransliterateOptions strict = TransliterateOptions.builder()
                .scheme(TransliterateOptions.Scheme.STRICT_ISO9)
                .lang("ru")
                .build();
        assertEquals("strict_iso9", strict.scheme());
        assertEquals("ru", strict.lang());

        // A null scheme falls back to DEFAULT.
        TransliterateOptions nullScheme = TransliterateOptions.builder().scheme(null).build();
        assertEquals("default", nullScheme.scheme());

        assertEquals("gost7034", TransliterateOptions.Scheme.GOST7034.token());
    }

    @Test
    void enumTokens() {
        assertEquals("latin", TargetScript.LATIN.token());
        assertEquals("cyrillic", TargetScript.CYRILLIC.token());

        assertEquals("NFC", NormalizationForm.NFC.token());
        assertEquals("NFKD", NormalizationForm.NFKD.token());

        assertEquals("universal", Platform.UNIVERSAL.token());
        assertEquals("windows", Platform.WINDOWS.token());
        assertEquals("posix", Platform.POSIX.token());
    }

    @Test
    void privateConstructorsAreInvocable() throws Exception {
        invokePrivateCtor(Disarm.class);
        invokePrivateCtor(com.disarm.internal.Native.class);
    }

    private static void invokePrivateCtor(Class<?> cls) throws Exception {
        Constructor<?> ctor = cls.getDeclaredConstructor();
        ctor.setAccessible(true);
        ctor.newInstance();
    }
}
