# Architecture

## Research question

Can an agent actively explore a fictional world it helped formalize, discover
causal gaps, and recursively extend the world's rule system while preserving
canon and artistic intent?

This repository implements the smallest honest machinery for that question. It
does not pretend that an LLM completion is a simulation. It separates:

1. **deterministic state and rule application** (Python);
2. **creative scenario generation and causal reasoning** (host agent);
3. **human approval** (a separate decision);
4. **regression validation** (deterministic checks).

## System diagram

```text
                    host agent / human
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
   exploration_       proposal JSON      approval / reject
   cases.json              │                 │
          │                │                 ▼
          ▼                │           RecursiveController
   Explorer ───────► CausalCritic ───► RuleArchitect
          │                │                 │
          ▼                ▼                 ▼
      RuleEngine       GapFinding        Proposal
          │                │                 │
          └────────────┬───┴─────────────────┘
                       ▼
                    World model
                 (world.json, canon)
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   regression gate             snapshot / rollback
```

## Module responsibilities

| Module | Responsibility | Explicit non-responsibility |
| --- | --- | --- |
| `model.py` | Dataclasses, serialization, validation, enums, fingerprints. | No reasoning. |
| `storage.py` | Atomic JSON, proposals, regressions, snapshots, run logs. | No canon decisions. |
| `ingest.py` | Markdown/JSON/YAML source ingestion and source index. | Does not invent rules from prose. |
| `engine.py` | Deterministic match/effect application, constraint checks, effect conflicts. | Not a physics engine or theorem prover. |
| `explorer.py` | Probe planning, external scenarios, scenario execution. | Not a creative author. |
| `critic.py` | Gap taxonomy, affected systems, dedupe keys, subjective confidence. | Not a calibrated classifier. |
| `mechanisms.py` | Offline mechanism-template library for demo/CI. | Not the primary reasoning path. |
| `architect.py` | Proposal construction, diffs, conflicts, validation, application. | Never applies without approval. |
| `controller.py` | Budgets, dedupe, stops, approval, regression, rollback. | No unbounded recursion. |
| `reporting.py` | Markdown run and modification reports. | Not a source of truth. |
| `cli.py` | Real argparse CLI. | No natural-language parser. |

## Data flow

### Exploration

1. `WorldStore.load_world()` validates `world.json`.
2. `Explorer.plan()` combines:
   - host-authored `exploration_cases.json`;
   - deterministic probes derived from semantic tags;
   - focus filtering and dedupe by scenario signature.
3. `RuleEngine.simulate()`:
   - resolves actor/target/location;
   - applies scenario assumptions to a clone;
   - checks prohibition/invariant constraints;
   - matches canon rules and sorts by priority/specificity/id;
   - applies effects with deterministic state-write conflict handling;
   - computes a fingerprint.
4. `CausalCritic.analyze()` emits a structured `GapFinding` or nothing.
5. `RecursiveController` deduplicates findings by mechanism family.
6. In scripted mode, `RuleArchitect.build_proposal()` creates a pending
   proposal. In host mode, the host writes one.

### Approval

1. CLI asks for confirmation unless `--yes`.
2. Controller reloads canon and proposal, checks world version and conflicts.
3. Controller snapshots `world.json` under `.rwb/snapshots/`.
4. `RuleArchitect.apply_proposal()`:
   - requires status `approved`;
   - adds or modifies rules;
   - retains old versions in `history`;
   - deprecates superseded rules;
   - increments `canon_version`.
5. Controller saves the world.
6. Controller runs the regression suite.
7. On failure, restores the snapshot and marks `regression_failed`.
8. Controller re-runs the proposal's test plan.
9. Report is written.

## Determinism and fingerprints

Given the same `world.json` and scenario, `RuleEngine` produces the same
observation. There is no randomness, wall-clock dependence, or network call in
simulation.

Rule ordering: `priority` descending, matcher specificity descending, rule id
ascending.

State-write semantics: `set_property` takes ownership of a target/property.
Later writes to that property are recorded in `suppressed_rule_ids` and are not
applied, so a lower-priority set cannot silently overwrite a higher-priority
one. Compatible `modify_property` effects may stack if no `set_property` owns
the property. This is a safety default, not a claim that priority is always
semantically correct.

Observation fingerprint hashes matched rule ids, effects, events, and
violations. Regression cases compare fingerprints before and after a patch.
Fingerprints prove **unchanged deterministic behavior**, not truth or quality.

## Conflict model

`RuleArchitect.detect_conflicts()` reports:

- **direct**:
  - duplicate rule id without an explicit modification diff;
  - declared `conflicts_with`;
  - one rule sets a property one way and another sets it differently;
  - add/remove of the same tag;
  - incompatible effects within one proposal.
- **potential**:
  - set/modify overlap;
  - overlapping prohibition;
  - redundant matchers that should probably be merged.

Conflicts are advisory data until approval. Direct conflicts block application
unless `accept_conflicts=True` is explicitly passed. The flag exists for
reviewed author decisions, not for silent automation.

## Canon and proposal lifecycle

```text
proposed ──approve──► approved ──apply──► applied
   │                     │
   │                     └── regression fail ──► regression_failed (canon rolled back)
   └──reject──► rejected (canon untouched)
```

Rules inside a proposal are `status: proposed`. Only `RuleArchitect` converts
them to `canon` during application.

## Why scripted and host modes coexist

- **Scripted templates** make CI and the offline demo possible. They are
  deterministic, inspectable, and explicitly labelled. They are also shallow.
- **Host mode** is the real product. The host agent reads the world and findings,
  then authors context-aware rules. This is where unusual physics, politics, and
  artistic intent are handled.

The skill pushes host mode for serious work and scripted mode for
demonstration/testing.

## Extension points

- Add a mechanism family in `mechanisms.py` and register it by primary system.
- Add semantic tags/probe families in `explorer.py`.
- Add effect kinds in `model.Effect` and `RuleEngine._apply_effect`.
- Add a regression baseline update path in the CLI.
- Add a schema migration if `schema_version` majors change.
- Add a host proposal validator for a domain-specific authoring format.
- Add snapshot backends (currently local files).

## Failure and recovery

- Atomic writes use a temp file next to the target and `os.replace`.
- Snapshots are written before any approval attempt.
- Regression failure is the only path that auto-rolls back.
- Stale proposals are rejected rather than rebased silently.
- No file locking is implemented. This is a single-user local tool; concurrent
  writers are out of scope.
- A YAML requirement fails closed with an install instruction.

## Design decisions

1. **Tags over formulas.** Semantic tags (`energized`, `liquid`, `fragile`) make
   rules reusable without a full physics model.
2. **Explicit approval over auto-patching.** The human remains the canon editor.
3. **Proposal diffs over chat logs.** Reviewability matters more than fluent
   prose.
4. **Regression over trust.** A plausible patch can still break stable behavior.
5. **No hidden LLM calls.** The runtime never sends world data anywhere.
6. **Small effect vocabulary.** If a rule needs arbitrary code, it is probably
   too specific for this layer.
