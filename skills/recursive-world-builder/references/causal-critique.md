# Causal Critique

The critic consumes a scenario and its deterministic observation, then emits a
structured finding or nothing.

## Structured finding

```json
{
  "scenario": "Character touches power line",
  "observation": "No electrical consequences defined",
  "gap_type": "undefined_interaction",
  "hypothesis": "Electrical interaction system missing",
  "confidence": 0.9,
  "confidence_kind": "subjective_agent_judgment",
  "calibrated": false,
  "affected_systems": ["electricity", "materials", "health"],
  "recommended_action": "propose_general_rule",
  "matched_rule_ids": [],
  "evidence": ["no canonical rule matched touch"],
  "dedupe_key": "undefined_interaction:electricity"
}
```

`confidence` is an agent's subjective ranking of how strongly the evidence
supports the hypothesis. It is **not** a calibrated probability, a p-value, or a
frequency estimate. The package forces `calibrated: false`; it rejects proposals
that claim calibration.

## Gap taxonomy

### `undefined_interaction`

Canon has no rule matching the scenario. This is a candidate gap.

Default recommendation: `propose_general_rule`.

Good response: find a mechanism family. In the power-line case, that means
conduction, insulation, energized media, and infrastructure damage — not
`if power_line: die()`.

Bad response: add a rule whose matcher names one demo entity.

Counterpoint: not every undefined interaction should be filled. A world can
deliberately leave the origin of magic unexplained. Ask whether explanation adds
causal leverage or destroys mystery.

### `explicit_violation`

The scenario matches a declared prohibition or invariant. The world is not
silent; it forbids the action.

Default recommendation: `review_not_error`.

Do not patch canon because a test scenario broke a law. This finding is useful
for testing enforcement, legitimacy, and consequences — not for rewriting the
law. If the user says the constraint itself is wrong, that is a separate,
explicit canon revision.

### `allowed_but_unrealistic`

A rule matched, and the outcome differs from a stated real-world expectation.
The fictional outcome wins unless it contradicts another canon statement.

Default recommendation: `preserve_canon`.

Example: a setting with one-tenth gravity. A dropped coin drifts. That is not a
bug. It is only a consistency question if another canon fact says gravity is
Earth-normal.

### `rule_conflict`

Multiple canon rules write the same state incompatibly, or a write is
suppressed because another rule already owns the property. This is an internal
consistency problem, not a missing mechanism.

Default recommendation: `review_conflict`.

Do not add a third rule to arbitrate. Surface the overlapping matchers, decide
which rule owns the state, narrow the matchers, or explicitly deprecate one.

### `missing_precondition`

Reserved for findings where a rule exists but an expected enabling state is
absent. The current deterministic engine reports undefined behavior rather than
this type; host-authored analysis may still produce it.

## Affected systems

The critic infers systems from target tags, actor tags, action tags, and matched
rules. Examples:

| Evidence | Systems |
| --- | --- |
| `energized`, `electrical` | electricity, materials, health |
| `water`, `liquid` | hydrology, materials |
| `vehicle`, `collide` | kinetics, materials, infrastructure |
| `hot`, `fire` | thermodynamics, materials, health |
| `law`, `institution` | society, law, institutions |
| `market`, `resource` | economy, exchange, resources |
| `persuade`, `character` | character, agency, knowledge |

The first system is the primary deduplication key. This is why touching a wire
and dropping a wire into water produce one `electricity` gap rather than two
unrelated proposals.

## Deduplication

Findings are deduplicated by `dedupe_key`:

- `undefined_interaction:<primary-system>`
- `explicit_violation:<primary-system>`
- `allowed_but_unrealistic:<primary-system>`
- `rule_conflict:<rule-ids>`

The key is intentionally coarser than the scenario. Ten probes of the same
missing mechanism should not create ten proposals. The controller also excludes
scenarios already run by action/actor/target/assumption signature.

Deduplication is conservative: it merges by mechanism family. If two genuinely
different gaps collapse into one, run a more specific focus or author scenarios
that exercise distinct systems.

## What counts as evidence

- A deterministic observation: matched rules, effects, events, constraints.
- The absence of a match for a meaningful interaction.
- A suppressed rule or conflicting write.
- A counterfactual test result after a patch.

What is **not** evidence by itself:

- The LLM's intuition that "this feels wrong".
- Real-world common sense against a declared fictional axiom.
- A dramatic possibility the author has not chosen to canonize.

## Review questions

Before proposing a rule, answer:

1. Is the gap truly undefined, or did I miss an existing rule?
2. Is the silence intentional artistic negative space?
3. What is the smallest mechanism that explains this and adjacent cases?
4. Which existing rule should be modified before adding a new one?
5. What dependencies does the new rule introduce?
6. What existing rules could it conflict with?
7. What counterfactual tests would falsify the proposal?
8. Does the change increase causal leverage, or just accumulate lore?

If the answer to 8 is "just lore", do not propose.

## Confidence guidance

Use confidence to communicate strength of evidence, not precision:

- `0.90–0.95`: direct undefined contact with a clear mechanism family; strong.
- `0.75–0.89`: undefined but scope uncertain.
- `0.55–0.74`: plausible classification, multiple interpretations.
- `<0.55`: speculative; keep it as a note, not a canon patch.

Never present these as probabilities. The package labels them
`subjective_agent_judgment` and keeps `calibrated: false`.
