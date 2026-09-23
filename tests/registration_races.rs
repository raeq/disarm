//! Registration is atomic with respect to its own limits and to the seal.
//!
//! A TLA+ model of the registration paths (`formal/tla/Concurrency`,
//! `Registration_rust.cfg`) found two check-then-act races in the public Rust API.
//! The seal check, the language-cap check and the write each took and released their
//! own lock, so:
//!
//! * two registrations racing for the last free slot could both pass the cap check
//!   and both insert, past `MAX_REGISTERED_LANGS`;
//! * a registration that had passed the seal check could land *after*
//!   `seal_registrations()` returned, which is the one thing a seal is for.
//!
//! The Python binding was never exposed: its entry points hold the GIL across the
//! whole call. The public Rust API does not.
//!
//! Sealing is irreversible and the tables are process-global, so both races run in
//! one test, in this binary of their own, cap first.

use std::collections::HashMap;
use std::sync::{Arc, Barrier};
use std::thread;

use disarm::api::{self, Transliterate};
use disarm::tables::MAX_REGISTERED_LANGS;
use disarm::ErrorKind;

/// A mapping large enough that building it holds a registration inside its
/// check-then-act window for a while, which is what makes the race observable.
fn wide_mapping() -> HashMap<String, String> {
    (0x4E00u32..0x4E00 + 20_000)
        .filter_map(char::from_u32)
        .map(|c| (c.to_string(), "x".to_owned()))
        .collect()
}

fn registered(prefix: &str) -> usize {
    api::list_langs()
        .iter()
        .filter(|l| l.starts_with(prefix))
        .count()
}

#[test]
fn registration_is_atomic_with_its_cap_and_with_the_seal() {
    // ---- the cap: fill to one below it, then race for the last slot ----
    for i in 0..MAX_REGISTERED_LANGS - 1 {
        api::register_lang(&format!("x-fill-{i}"), HashMap::new()).expect("below the cap");
    }
    let racers = 16;
    let barrier = Arc::new(Barrier::new(racers));
    let outcomes: Vec<_> = (0..racers)
        .map(|i| {
            let barrier = Arc::clone(&barrier);
            let mapping = wide_mapping();
            thread::spawn(move || {
                barrier.wait();
                api::register_lang(&format!("x-race-{i}"), mapping)
            })
        })
        .collect::<Vec<_>>()
        .into_iter()
        .map(|h| h.join().expect("no panic"))
        .collect();
    let won = outcomes.iter().filter(|r| r.is_ok()).count();
    assert_eq!(won, 1, "{won} registrations took the one free slot");
    assert!(outcomes
        .iter()
        .filter_map(|r| r.as_ref().err())
        .all(|e| e.kind() == ErrorKind::ResourceLimit));
    assert_eq!(
        registered("x-fill-") + registered("x-race-"),
        MAX_REGISTERED_LANGS
    );

    // ---- the seal: nothing lands after seal_registrations() returns ----
    // Re-registering an existing code is allowed at the cap, so the writers overwrite
    // filler codes, each write with a value of its own; the values read back right
    // after the seal must be the ones still there once every writer has stopped.
    let writers = 8;
    let codes: Vec<String> = (0..writers).map(|i| format!("x-fill-{i}")).collect();
    let read_back = |codes: &[String]| -> Vec<String> {
        codes
            .iter()
            .map(|c| Transliterate::new().lang(c).run("\u{4E00}").into_owned())
            .collect()
    };
    let barrier = Arc::new(Barrier::new(writers + 1));
    let handles: Vec<_> = codes
        .clone()
        .into_iter()
        .map(|code| {
            let barrier = Arc::clone(&barrier);
            thread::spawn(move || {
                let mut mapping = wide_mapping();
                barrier.wait();
                let mut landed = 0usize;
                loop {
                    mapping.insert("\u{4E00}".to_owned(), format!("v{landed}"));
                    if api::register_lang(&code, mapping.clone()).is_err() {
                        return landed;
                    }
                    landed += 1;
                }
            })
        })
        .collect();
    barrier.wait();
    thread::sleep(std::time::Duration::from_millis(50));
    api::seal_registrations();
    let at_seal = read_back(&codes);
    let landed: usize = handles
        .into_iter()
        .map(|h| h.join().expect("no panic"))
        .sum();
    assert!(landed > 0, "the writers never ran before the seal");
    assert_eq!(
        read_back(&codes),
        at_seal,
        "a registration landed after seal_registrations() returned"
    );
}
