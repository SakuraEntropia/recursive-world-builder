# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-22

### Added

- Initial runnable implementation of Recursive World Builder.
- `World` model with entities, locations, properties, rules, events,
  relationships, constraints, canon facts, source documents, history, and a
  regression suite.
- Deterministic rule engine with tag/property matchers, declarative effects,
  priority ordering, state-write suppression, and constraint checks.
- Explorer with deterministic probes for physics, biology, society, economy, and
  character interactions, plus host-authored `exploration_cases.json`.
- Causal Critic with `undefined_interaction`, `explicit_violation`,
  `allowed_but_unrealistic`, and `rule_conflict` classifications.
- Rule Architect with proposal diffs, dependencies, conflict detection,
  in-place rule modification, and explicit application.
- Recursive Controller with hard budgets, finding deduplication, finite stop
  reasons, approval, snapshots, regression gate, automatic rollback, and
  counterfactual re-tests.
- CLI: `init`, `validate`, `summary`, `explore`, `proposals`, `show`, `approve`,
  `reject`, `propose`, `regressions`, `rollback`, `sources`.
- Agent Skill bundle with `SKILL.md` and references.
- Electric City demo with an offline scripted architect.
- Slow-Fall Plateau demo for `allowed_but_unrealistic` behavior.
- Markdown/JSON/YAML ingestion with documented Markdown format and fenced world
  fragments.
- pytest acceptance and unit tests, Ruff checks, GitHub Actions CI.

### Known limitations

- Single-action scenarios; no continuous physics, markets, or minds.
- Scripted mechanism templates are shallow by design.
- Regression fingerprints prove unchanged deterministic behavior, not quality.
- Single-user local storage; no file locking.
