package com.disarm.internal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import com.disarm.DisarmException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

/** Covers {@link NativeLoader}'s pure platform-mapping helpers and extraction. */
class NativeLoaderTest {

    @Test
    void osTokenNormalization() {
        assertEquals("darwin", NativeLoader.osToken("Mac OS X"));
        assertEquals("darwin", NativeLoader.osToken("Darwin"));
        assertEquals("windows", NativeLoader.osToken("Windows 11"));
        assertEquals("linux", NativeLoader.osToken("Linux"));
        assertThrows(DisarmException.class, () -> NativeLoader.osToken("SunOS"));
    }

    @Test
    void archTokenNormalization() {
        assertEquals("aarch64", NativeLoader.archToken("aarch64"));
        assertEquals("aarch64", NativeLoader.archToken("arm64"));
        assertEquals("x86_64", NativeLoader.archToken("x86_64"));
        assertEquals("x86_64", NativeLoader.archToken("amd64"));
        assertThrows(DisarmException.class, () -> NativeLoader.archToken("sparc"));
    }

    @Test
    void libFileNamePerOs() {
        assertEquals("disarm_jni.dll", NativeLoader.libFileName("windows"));
        assertEquals("libdisarm_jni.dylib", NativeLoader.libFileName("darwin"));
        assertEquals("libdisarm_jni.so", NativeLoader.libFileName("linux"));
    }

    @Test
    void resourcePathShape() {
        assertEquals(
                "/com/disarm/native/darwin-aarch64/libdisarm_jni.dylib",
                NativeLoader.resourcePath("darwin-aarch64", "libdisarm_jni.dylib"));
    }

    @Test
    void osArchIsWellFormed() {
        String tag = NativeLoader.osArch();
        assertNotNull(tag);
        assertTrue(tag.contains("-"), tag);
    }

    @Test
    void overridePathReflectsSystemProperty() {
        String prev = System.getProperty("disarm.native.lib");
        try {
            System.setProperty("disarm.native.lib", "/tmp/whatever.dylib");
            assertEquals("/tmp/whatever.dylib", NativeLoader.overridePath());
        } finally {
            if (prev == null) {
                System.clearProperty("disarm.native.lib");
            } else {
                System.setProperty("disarm.native.lib", prev);
            }
        }
    }

    @Test
    void overridePathNullWhenUnset() {
        String prev = System.getProperty("disarm.native.lib");
        System.clearProperty("disarm.native.lib");
        try {
            // Only meaningful when the env var is also unset.
            assumeTrue(System.getenv("DISARM_NATIVE_LIB") == null);
            assertNull(NativeLoader.overridePath());
        } finally {
            if (prev != null) {
                System.setProperty("disarm.native.lib", prev);
            }
        }
    }

    @Test
    void extractBundledLibraryReturnsRealFile() {
        // The Gradle build stages the host cdylib into resources; extraction of the
        // real resource must yield a non-empty temp file.
        String os = NativeLoader.osToken(System.getProperty("os.name"));
        String resource = NativeLoader.resourcePath(NativeLoader.osArch(), NativeLoader.libFileName(os));
        Path extracted = NativeLoader.extractBundledLibrary(resource);
        assertTrue(Files.exists(extracted), "extracted temp file should exist");
        assertTrue(sizeOf(extracted) > 0, "extracted temp file should be non-empty");
    }

    @Test
    void extractMissingResourceThrows() {
        assertThrows(
                DisarmException.class,
                () -> NativeLoader.extractBundledLibrary("/com/disarm/native/nope-nope/libdisarm_jni.so"));
    }

    @Test
    void resolveLibraryPathUsesOverride() {
        String prev = System.getProperty("disarm.native.lib");
        try {
            System.setProperty("disarm.native.lib", "/tmp/override.dylib");
            assertEquals("/tmp/override.dylib", NativeLoader.resolveLibraryPath());
        } finally {
            if (prev == null) {
                System.clearProperty("disarm.native.lib");
            } else {
                System.setProperty("disarm.native.lib", prev);
            }
        }
    }

    @Test
    void resolveLibraryPathExtractsWhenNoOverride() {
        String prev = System.getProperty("disarm.native.lib");
        System.clearProperty("disarm.native.lib");
        try {
            assumeTrue(System.getenv("DISARM_NATIVE_LIB") == null);
            Path p = Path.of(NativeLoader.resolveLibraryPath());
            assertTrue(Files.exists(p), "resolved library path should exist");
        } finally {
            if (prev != null) {
                System.setProperty("disarm.native.lib", prev);
            }
        }
    }

    @Test
    void loadIsIdempotent() {
        // The native library is already loaded by the time any test runs (Native's
        // static init); a further call must be a no-op, not a re-load.
        NativeLoader.load();
        NativeLoader.load();
    }

    @Test
    void privateConstructorIsInvocable() throws Exception {
        var ctor = NativeLoader.class.getDeclaredConstructor();
        ctor.setAccessible(true);
        ctor.newInstance();
    }

    private static long sizeOf(Path p) {
        try {
            return Files.size(p);
        } catch (Exception e) {
            return -1;
        }
    }
}
