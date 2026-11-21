# Development

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

This installs the `rwb` console script and PyYAML for the optional YAML path.

## Checks

```bash
python -m pytest
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
```

Run the offline demo after changes that touch the rule engine, critic, or
controller:

```bash
python scripts/run_demo.py --approve
```

## Test layout

```text
tests/
├── conftest.py                  # temp copies of example worlds
├── fixtures/
│   ├── conflict_world/          # direct rule conflict
│   └── markdown_world/          # Markdown + fenced JSON ingestion
├── unit/
│   ├── test_model.py            # model, validation, ingestion
│   ├── test_engine.py           # rule matching, effects, constraints
│   ├── test_critic.py           # three classifications
│   └── test_architect.py        # proposal conflicts, approval, modification
└── integration/
    ├── test_acceptance.py       # required end-to-end guarantees
    └── test_cli.py              # CLI commands and module entry point
```

Acceptance coverage maps to the project requirements:

1. valid world loads;
2. undefined interaction detected;
3. structured proposal generated;
4. direct conflict detected;
5. rejection leaves canon unchanged;
6. approval updates canon;
7. recursion stops within a budget;
8. regression suite stays green; failed regression rolls back.

## Add a mechanism family

1. Add tags/probes in `explorer.py` if the deterministic planner should discover
   the gap.
2. Add a builder method in `mechanisms.py` keyed by primary system.
3. Register it in `MechanismLibrary._builders`.
4. Include:
   - general tag-based matchers, not entity ids;
   - dependencies;
   - multiple counterfactual tests;
   - expected impacts and scope limits;
   - `special_case: false` unless genuinely unique.
5. Add tests for both detection and approval.
6. Run the demo to make sure unrelated regressions still pass.

Host-authored proposals do not require a mechanism template. They are the
preferred path for unusual settings.

## Add a gap type

1. Add to `GapType` in `model.py`.
2. Emit it from `CausalCritic.analyze`.
3. Decide its `Recommendation` and whether `RuleArchitect` may propose.
4. Update `references/causal-critique.md`.
5. Add a positive and a negative test.

## Add an effect kind

1. Add to `Effect.VALID_KINDS` and validation.
2. Implement in `RuleEngine._apply_effect`.
3. Ensure it is included in observation records and fingerprints.
4. Update `references/world-schema.md`.
5. Add an engine test and a conflict-detection test if it writes state.

## Schema changes

The current schema is `1.0`. A major bump requires:

- a loader migration or a hard rejection;
- updated example worlds;
- updated docs;
- tests for old and new files.

Minor additive fields are fine if `World.from_dict` tolerates missing values.

## CLI changes

The CLI is a real parser in `cli.py`, not a natural-language shim. Keep:

- non-zero exits for failures;
- no prompts when `--yes` is supplied;
- no canon changes from read-only commands;
- explicit conflict output.

## Reports

`reporting.py` owns Markdown. Reports should keep deterministic observations,
agent inference, and approval decisions visibly separate. Do not describe a
proposal as a verified fact.

## Privacy

Do not commit:

- API keys, tokens, `.env` files;
- private world documents;
- `.rwb/` snapshots or run logs;
- `demo-output/` or generated `reports/`.

The runtime makes no network calls. Host LLM usage is outside this package; its
provider policy applies.

## Release checklist

- bump `version` in `pyproject.toml` and `__init__.py`;
- update `CHANGELOG.md`;
- run pytest and Ruff;
- run the offline demo;
- verify `world.json` in examples stays at canon v1;
- build/install the wheel in a clean environment;
- only then tag and push.
