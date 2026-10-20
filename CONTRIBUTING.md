# Contributing to ReadmeForge

Thanks for helping improve developer documentation tooling.

## Development setup

~~~bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
~~~

## Contribution principles

- Add fixture-based tests for normal, malformed-input, and cross-platform cases.
- Keep inspection local: never execute analyzed project code or make network requests.
- Bound directory traversal and file reads.
- Clearly distinguish observed metadata from inferred commands and unknown behavior.
- Keep Markdown output deterministic and escape untrusted values.
- Never overwrite an existing README without an explicit force option.
- Update documentation and changelog for user-visible changes.

## Pull request checklist

- [ ] Tests are added or updated.
- [ ] python -m pytest passes.
- [ ] python -m ruff check src tests passes.
- [ ] New reads have a documented size limit and failure behavior.
- [ ] Generated output remains deterministic and does not embed source contents.
- [ ] README claims do not overstate features, test success, adoption, or performance.

Never submit credentials, private source code, or confidential repository dumps in public issues.
