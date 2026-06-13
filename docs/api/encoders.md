# Output Encoders

Context-explicit **output encoders** — correct for a *specific* output sink, applied at the sink, exactly once.

These are deliberately **standalone terminal functions, not pipeline steps**: output encoding depends on the destination context (HTML element vs. attribute vs. URL component), which a context-free [pipeline](pipelines.md) cannot know. Baking an encoder into a pipeline invites double-encoding, wrong-context escaping, and storing pre-escaped text.

They do **not** make disarm an XSS/injection framework — they are narrow, context-pinned encoders, the explicit exception to disarm's ["not an output sanitizer"](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md) positioning. Run them at output, *after* (not instead of) the input-normalization layer.

## escape_html

::: disarm.escape_html

---

## percent_encode

::: disarm.percent_encode

### Component

::: disarm.Component

---

## strip_log_injection

Neutralizes the characters that let untrusted text forge log records (CRLF / NEL / LS / PS), corrupt parsers (NUL / C0 / C1 controls), or hijack a terminal that views the log (ANSI escape introducers / DEL). It makes a log line safe to **write** — it owns the log-record and operator-terminal sinks.

It makes **no HTML-log-viewer-safety claim**: rendering attacker text in an HTML dashboard (Kibana/Grafana) is stored/second-order XSS, which the *viewer* must output-encode with [`escape_html`](#escape_html). It preserves `<`, `>`, `&` precisely so nothing mistakes it for viewer-safe output, and it is not a defense against logging-framework interpolation (log4shell). See the [Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md).

::: disarm.strip_log_injection
