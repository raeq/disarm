# Security Policy

## Supported versions

Only the latest release on PyPI is actively maintained for security fixes.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report them privately via GitHub's
[Security Advisories](https://github.com/raeq/translit/security/advisories/new)
feature. We will acknowledge the report within 5 business days and aim to
publish a fix within 30 days for confirmed issues.

Please include:
- A description of the vulnerability
- Steps to reproduce (minimal example)
- Potential impact assessment

## Scope

translit is a pure text-transformation library with no network access, file
system writes, or code execution. Known security-relevant features include:

- **Homoglyph detection** — Unicode TR39 confusable character normalization
- **BIDI attack prevention** — bidirectional override character stripping
- **Path traversal protection** — `..` sequence collapse in filename sanitization
- **Encoding detection** — `chardetng` / `encoding_rs` from Mozilla (no arbitrary code)
