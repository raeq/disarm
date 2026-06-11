# translit-rs — renamed to `disarm`

**DEPRECATED.** `translit-rs` has been renamed to **[`disarm`](https://pypi.org/project/disarm/)**
and is no longer maintained under the old name.

## Migrate

```bash
pip uninstall translit-rs
pip install disarm
```

```python
# before
import translit

# after
import disarm
```

`translit-rs 0.8.2` is a thin compatibility shim: installing it pulls in `disarm`
and re-exports its API, so existing `import translit` code keeps working — but it
raises a `DeprecationWarning` and will not receive further updates. Switch to
`import disarm`.

## What changed in the rename

- Distribution + import name unified: `pip install disarm`, `import disarm`.
- **Breaking:** base exception `TranslitError` → `DisarmError` (aliased in this
  shim for back-compat; the subclasses `InvalidArgumentError` /
  `ResourceLimitError` / `UnsupportedError` keep their names). `DisarmError` is
  still a `ValueError` subclass.
- **Breaking:** context-dictionary env var `TRANSLIT_DICT_DIR` → `DISARM_DICT_DIR`.
- The transform API — `transliterate()`, `normalize()`, `slugify()`, and the
  security/pipeline helpers — is otherwise unchanged.

The last functional release under the old name was `translit-rs 0.8.1`.

- Project: <https://github.com/raeq/disarm>
- Docs: <https://docs.disarm.dev>
- Rename rationale: <https://github.com/raeq/disarm/issues/264>
