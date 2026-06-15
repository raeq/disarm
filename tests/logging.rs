//! #208 logging behaviour — built only with `--features log`. Proves the
//! redaction contract (default-level records carry NO input/output content) and
//! that the instrumented boundaries emit at the expected levels.
#![cfg(feature = "log")]

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use log::{Level, Log, Metadata, Record};

static RECORDS: OnceLock<Mutex<Vec<(Level, String)>>> = OnceLock::new();
fn records() -> &'static Mutex<Vec<(Level, String)>> {
    RECORDS.get_or_init(|| Mutex::new(Vec::new()))
}

struct Capture;
impl Log for Capture {
    fn enabled(&self, _: &Metadata) -> bool {
        true
    }
    fn log(&self, r: &Record) {
        records()
            .lock()
            .unwrap()
            .push((r.level(), r.args().to_string()));
    }
    fn flush(&self) {}
}
static LOGGER: Capture = Capture;

fn init() {
    let _ = log::set_logger(&LOGGER);
    log::set_max_level(log::LevelFilter::Trace);
}

fn drain() -> Vec<(Level, String)> {
    std::mem::take(&mut records().lock().unwrap())
}

#[test]
fn redaction_and_boundaries() {
    init();
    let _ = drain();

    // A sentinel that must NEVER appear in any default-level record — it is the
    // input text, a register_lang *value*, and a register_replacements *key*, so
    // the test fails if the instrumentation logs any of that content.
    let sentinel = "SENTINEL_café";
    // Embed raw CR/LF/NEL so the injection-safety assertion below is non-trivial:
    // a metadata callsite that ever interpolated this input with `{}` instead of
    // `{:?}` would forge a log line, and the no-raw-newline check would catch it.
    let input = format!("{sentinel}_Москва\r\n\u{0085}_{sentinel}");

    // DEBUG: transliterate completion (the wrapper boundary, not the hot loop).
    let _ = disarm::api::transliterate(&input);

    // INFO: config/state mutations. The mapping value / replacement key carry the
    // sentinel; the records must log only the code + counts.
    let mut mappings = HashMap::new();
    mappings.insert("ж".to_owned(), sentinel.to_owned());
    disarm::api::register_lang("x-208-log", mappings).expect("registration before seal succeeds");

    let mut repls = HashMap::new();
    repls.insert(sentinel.to_owned(), "x".to_owned());
    disarm::api::register_replacements(repls).expect("registration before seal succeeds");

    disarm::api::seal_registrations();

    let recs = drain();
    assert!(
        !recs.is_empty(),
        "expected records from the instrumented boundaries"
    );

    // Hard requirement: no record leaks content at any captured level.
    for (level, msg) in &recs {
        assert!(
            !msg.contains(sentinel) && !msg.contains("café") && !msg.contains("Москва"),
            "record leaked content at {level}: {msg}"
        );
    }

    // Injection-safety: no record body may carry a raw log-forging character
    // (CR/LF/NEL/LS/PS). The metadata callsites format untrusted values with
    // `{:?}`, which escapes these; this assertion turns that convention into an
    // enforced guarantee that a future `{}` regression would trip.
    for (level, msg) in &recs {
        assert!(
            !msg.contains(['\r', '\n', '\u{0085}', '\u{2028}', '\u{2029}']),
            "record carries a raw log-forging character at {level}: {msg:?}"
        );
    }

    // The expected boundary records were emitted at the expected levels.
    assert!(
        recs.iter()
            .any(|(l, m)| *l == Level::Debug && m.starts_with("transliterate:")),
        "missing transliterate DEBUG record"
    );
    assert!(
        recs.iter()
            .any(|(l, m)| *l == Level::Info && m.starts_with("register_lang:")),
        "missing register_lang INFO record"
    );
    assert!(
        recs.iter()
            .any(|(l, m)| *l == Level::Info && m.starts_with("register_replacements:")),
        "missing register_replacements INFO record"
    );
    assert!(
        recs.iter()
            .any(|(l, m)| *l == Level::Info && m.contains("sealed")),
        "missing seal INFO record"
    );
}
