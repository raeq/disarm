package dev.disarm;

import dev.disarm.internal.Native;
import java.lang.ref.Cleaner;
import java.util.List;
import java.util.Objects;

/**
 * A reusable anomaly lexicon (common-word list) built once and reused across
 * {@link Disarm#hasAnomalies(String, Lexicon)} calls.
 *
 * <p>{@code hasAnomalies} with a raw word list rebuilds the internal set on every
 * call; a {@code Lexicon} folds the words into that set a single time in its
 * constructor, avoiding the per-call rebuild.
 *
 * <p>Holds a native resource. {@link AutoCloseable} — use try-with-resources — with
 * a {@link Cleaner} backstop that frees the native handle on garbage collection if
 * {@code close()} is not called.
 */
public final class Lexicon implements AutoCloseable {

    private static final Cleaner CLEANER = Cleaner.create();

    private final long handle;
    private final Cleaner.Cleanable cleanable;
    private volatile boolean closed = false;

    /** Build a reusable lexicon from a word list. */
    public Lexicon(List<String> words) {
        Objects.requireNonNull(words, "words");
        this.handle = Native.lexiconNew(words.toArray(new String[0]));
        this.cleanable = CLEANER.register(this, new FreeAction(handle));
    }

    /** The opaque native handle, for {@link Disarm} to pass to {@code hasAnomalies}. */
    long handle() {
        if (closed) {
            throw new IllegalStateException("Lexicon has been closed");
        }
        return handle;
    }

    @Override
    public void close() {
        if (!closed) {
            closed = true;
            cleanable.clean();
        }
    }

    private record FreeAction(long handle) implements Runnable {
        @Override
        public void run() {
            Native.lexiconFree(handle);
        }
    }
}
