package dev.disarm;

import dev.disarm.internal.Native;
import java.lang.ref.Cleaner;
import java.util.Objects;

/**
 * A reusable, compiled named-policy pipeline (see {@link Disarm#getPipeline}).
 *
 * <p>The profile's steps are validated and compiled once in the native layer; the
 * resulting handle is then applied to any number of inputs via {@link #process},
 * paying the build cost a single time rather than per call.
 *
 * <p>Holds a native resource. {@link AutoCloseable} — use try-with-resources — and,
 * as a backstop against a forgotten {@code close()}, a {@link Cleaner} frees the
 * native handle if this object is garbage-collected first. Not safe for concurrent
 * {@code close()} / {@code process()} from multiple threads.
 */
public final class Pipeline implements AutoCloseable {

    private static final Cleaner CLEANER = Cleaner.create();

    private final long handle;
    private final Cleaner.Cleanable cleanable;
    private volatile boolean closed = false;

    Pipeline(long handle) {
        this.handle = handle;
        // The cleaning action must not capture `this` (it would never be GC'd);
        // it captures only the primitive handle.
        this.cleanable = CLEANER.register(this, new FreeAction(handle));
    }

    /** Run the pipeline over {@code text}, returning the cleaned string. */
    public String process(String text) {
        if (closed) {
            throw new IllegalStateException("Pipeline has been closed");
        }
        Objects.requireNonNull(text, "text");
        return Native.pipelineProcess(handle, text);
    }

    /**
     * A copy of this pipeline whose confusable passes fold under {@code digitPolicy} (#646).
     * Throws {@link DisarmInvalidArgumentException} when the profile has no confusables step
     * and the policy is not the default: a setting that would never run is refused rather
     * than kept. The copy holds its own native handle — close it too.
     */
    public Pipeline withDigitPolicy(DigitPolicy digitPolicy) {
        if (closed) {
            throw new IllegalStateException("Pipeline has been closed");
        }
        Objects.requireNonNull(digitPolicy, "digitPolicy");
        long fresh = Native.pipelineWithDigitPolicy(handle, digitPolicy.token());
        if (fresh == 0) {
            throw new IllegalStateException("Pipeline handle is not registered");
        }
        return new Pipeline(fresh);
    }

    /** Free the native handle. Idempotent. */
    @Override
    public void close() {
        if (!closed) {
            closed = true;
            cleanable.clean(); // runs FreeAction exactly once and de-registers
        }
    }

    /** Frees the native pipeline; a {@code record} so it captures only the handle. */
    private record FreeAction(long handle) implements Runnable {
        @Override
        public void run() {
            Native.pipelineFree(handle);
        }
    }
}
