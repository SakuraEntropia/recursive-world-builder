# Contributing

Contributions are welcome. This project touches fictional canon, so the
non-negotiable rule is: **exploration and proposals must never silently modify
canon.**

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests scripts
```

## Before opening a PR

- Add or update tests for behavior changes.
- Keep deterministic engine behavior deterministic.
- Update `skills/recursive-world-builder/references/` if the schema, gap types,
  or workflow changes.
- Run the offline demo:
  `python scripts/run_demo.py --approve`.
- Confirm `examples/electric_city/world.json` is still at `canon_version: 1`.
- Do not commit `.rwb/`, `demo-output/`, `reports/`, `.env` files, API keys, or
  private world material.

## Design constraints

- Prefer general tag/property mechanisms over entity-specific exceptions.
- Do not add an LLM/network dependency to the runtime without an explicit
  design discussion. Host reasoning belongs to the host agent.
- Do not describe subjective confidence as calibrated probability.
- Do not weaken the approval boundary for convenience.
- Keep the effect vocabulary small. Arbitrary code execution in rules is out of
  scope.
- Preserve intentional fictional deviations from reality.

## Adding a mechanism

See [`docs/development.md`](docs/development.md#add-a-mechanism-family).

## Commit style

Conventional-ish prefixes are appreciated but not enforced:

```text
feat: add thermal conduction mechanism
fix: roll back on regression failure
docs: clarify allowed_but_unrealistic
test: cover stale proposal rejection
```

## Reporting bugs

Include:

- the command;
- Python version;
- relevant `world.json` fragment (redact private material);
- expected vs actual behavior;
- whether the bug is in deterministic simulation, proposal validation, or CLI.

## License

By contributing, you agree that your contribution is licensed under the MIT
License.
