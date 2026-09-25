package dev.disarm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * {@code listLangs}, {@code listProfiles} and {@code reverseLangs} return what the other
 * bindings return (#981). The expected lists are {@code tests/fixtures/introspection_lists.tsv},
 * which {@code tests/test_jvm_api_page.py} writes from the Python binding and holds equal to
 * it, so this compares the JVM to Python through one file rather than through a copy.
 */
class IntrospectionListsTest {

    private static final String FIXTURE = "tests/fixtures/introspection_lists.tsv";

    /** The fixture, found by walking up from Gradle's working directory to the repository. */
    private static Map<String, List<String>> fixture() throws IOException {
        Path dir = Path.of("").toAbsolutePath();
        while (dir != null && !Files.exists(dir.resolve(FIXTURE))) {
            dir = dir.getParent();
        }
        if (dir == null) {
            throw new IOException(FIXTURE + " not found above " + Path.of("").toAbsolutePath());
        }
        Map<String, List<String>> rows = new HashMap<>();
        for (String line : Files.readAllLines(dir.resolve(FIXTURE), StandardCharsets.UTF_8)) {
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            String[] cells = line.split("\t", 2);
            rows.put(cells[0], Arrays.asList(cells[1].split(",")));
        }
        return rows;
    }

    @Test
    void listLangsIsWhatEveryBindingReturns() throws IOException {
        assertEquals(fixture().get("list_langs"), Disarm.listLangs());
    }

    @Test
    void listProfilesIsWhatEveryBindingReturns() throws IOException {
        assertEquals(fixture().get("list_profiles"), Disarm.listProfiles());
    }

    @Test
    void reverseLangsIsWhatEveryBindingReturns() throws IOException {
        assertEquals(fixture().get("reverse_langs"), Disarm.reverseLangs());
    }

    @Test
    void everyListedProfileOpensAPipelineThatSaysWhatItIsFor() {
        for (String profile : Disarm.listProfiles()) {
            try (Pipeline pipeline = Disarm.getPipeline(profile)) {
                assertFalse(pipeline.purpose().isBlank(), profile);
            }
        }
    }

    @Test
    void theListsAreUnmodifiable() {
        assertThrows(UnsupportedOperationException.class, () -> Disarm.listLangs().add("xx"));
    }
}
