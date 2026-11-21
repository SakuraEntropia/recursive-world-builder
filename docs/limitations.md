# Limitations and Roadmap

## What this is not

- **Not a physics engine.** There is no continuous integration, collision mesh,
  fluid solver, thermodynamics solver, or units system. Rule magnitudes are
  hand-authored.
- **Not a formal verifier.** Rules are matched and applied symbolically. There is
  no theorem prover, model checker, or proof that a rule set is satisfiable.
- **Not a market or society simulator.** The economy and society templates emit
  events and tags. They do not clear markets, model legitimacy, or simulate
  institutions.
- **Not a multi-agent system.** Explorer, Critic, and Architect are components of
  one pipeline, not autonomous negotiators.
- **Not a calibrated classifier.** Confidence is a subjective agent judgement.
  The schema forces `calibrated: false`.
- **Not an LLM API client.** Host reasoning happens in the calling agent. The
  Python package makes no network requests.

## Current implementation limits

### Rule language

- Single-entity property matching; no relational traversal in rules.
- No arithmetic expressions beyond numeric add/set.
- No probabilistic rules.
- No time, duration, or ordered multi-step scenarios. Each scenario is one action.
  Counterfactual combinations are expressed by assumptions or separate tests.
- `move_entity` exists but has no pathfinding or containment hierarchy.
- Invariants are evaluated as action matchers, not arbitrary post-state formulas.
- Conflicts are structural approximations; they can miss semantic contradictions
  expressed only in prose.

### Exploration

- The deterministic planner uses tag heuristics. It does not understand plot,
  character motivation, or theme.
- Host-authored scenarios are necessary for meaningful self-play.
- The planner can miss unusual domains with no matching tags.
- Deduplication can merge distinct gaps if they share a primary system.
- `no_candidate_scenarios` is not completeness.

### Proposal generation

- Scripted templates are generic and can be superficial.
- Host-authored proposals are only as good as the host's reasoning.
- The validator checks structure and obvious conflicts, not narrative quality.
- There is no automatic proof that a new rule is consistent with free-form canon.
- `world_version` freshness is strict; proposals cannot be rebased automatically.

### Regression

- Fingerprints compare deterministic outcomes, not artistic intent.
- A regression pass means "nothing we tested changed", not "the world is good".
- Changing a regression baseline is a deliberate human action
  (`rwb regressions --update`) and is not itself regression-tested.
- There is no coverage metric for the regression suite.

### Storage and operation

- Single-user, no file locking. Concurrent approvals can race.
- No database; whole-world JSON reads/writes.
- Snapshots are local files; no remote backup.
- No encryption at rest. Do not store secrets in world files.
- YAML requires optional PyYAML.

## Design risks

1. **Template overreach.** A generic-sounding template can still be wrong for a
   setting. Host mode exists for this reason.
2. **Canon explosion.** An agent can propose many plausible mechanisms. The
   controller caps rules, but the human must still reject low-value patches.
3. **False confidence.** A 0.92 subjective score looks precise. The schema and
   reports keep the uncalibrated label, but readers may still over-trust it.
4. **Regression myopia.** Passing existing tests can hide new contradictions in
   untested interactions.
5. **Narrative flattening.** Explaining every mystery can damage a setting. The
   skill explicitly permits deliberate negative space.

## Roadmap

Priorities, in order:

1. **Richer proposal schema for host agents** — domain-specific evidence,
   rejected alternatives, and explicit "do not canonize" notes.
2. **Multi-step scenarios** — sequences of actions with intermediate state, so a
   line can fall into water and then a character can enter in one test.
3. **Relational rules** — traverse `supports`, `owns`, `located_in` without
   hard-coding entity ids.
4. **Post-state invariants** — declarative consistency checks beyond action
   prohibitions.
5. **Better conflict semantics** — distinguish stacking modifiers from
   contradictory writes.
6. **Regression coverage tools** — report which systems/cases are untested.
7. **World pack format** — portable bundle of canon, sources, proposals, and
   snapshots.
8. **Web UI** — visual rule graph and approval diff. Not planned until the core
   semantics are stable.
9. **Optional LLM adapters** — only if they preserve the explicit reasoning
   boundary and never auto-apply canon.
10. **Formal export** — emit rules to a constraint solver or Datalog for
    verification, clearly separated from the current deterministic engine.

## Non-goals

- Unreal/Unity integration.
- 3D asset generation.
- Real-time simulation.
- Large-scale multi-agent societies.
- A universal physics ontology.
- Replacing the author's taste.

The project is deliberately small enough to audit. If a feature would make the
canon boundary less visible, it belongs outside the core.
