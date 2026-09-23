# A note on AI-assisted contributions

AI tools are fine to use — many of us use them. The bar is simple and it's the same
bar that has always applied: **you must be able to reproduce and stand behind what you
submit.**

- For a **bug or security report**, that means a minimal reproduction that actually
  runs against the current release, and identifying the specific documented behavior or
  invariant you believe is wrong.
- For a **pull request**, that means a test that *fails before* your change and *passes
  after*, and that the full CI suite is green.

Reports or PRs that are clearly machine-generated, can't be reproduced, and whose author
can't answer follow-up questions will be closed without extended back-and-forth. This
isn't hostility toward AI — it's the cost of a maintainer's time. Speculative
"there might be a buffer overflow here" reports with no reproduction are the one thing
that genuinely drains a small project.

## Attribute the assistant

If an AI coding **agent** helped produce a commit, that commit **must** carry an
`Assisted-by:` trailer naming the agent and model, following the Linux kernel's
[coding-assistants guidance](https://docs.kernel.org/process/coding-assistants.html).
Using an assistant is welcome and encouraged; **not disclosing it is not** — the
attribution is required, not optional.

The format is `Assisted-by: AGENT_NAME:MODEL_VERSION [analysis-tools]`, alongside your
own DCO sign-off:

```
Signed-off-by: Jane Developer <jane@example.com>
Assisted-by: Claude:claude-3-opus coccinelle sparse
```

Use the **actual** agent and the model version you used (model ids change — record the
one in effect for that commit), and append specialised analysis tools if relevant
(e.g. `coccinelle`, `sparse`). Do **not** list ordinary tools like git, the compiler,
or your editor.

An assistant **must never** add a `Signed-off-by:` or `Co-developed-by:` trailer — only a
human can certify the [DCO](../CONTRIBUTING.md#sign-your-work-developer-certificate-of-origin). You, the
human submitter, review the change, add your own `Signed-off-by:`, and take full
responsibility for it. In short: **`Assisted-by:` is attribution; `Signed-off-by:` is
accountability** — every AI-assisted commit needs both, and they are never the same line.
