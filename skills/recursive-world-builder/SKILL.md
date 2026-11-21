---
name: recursive-world-builder
description: Explore an existing fictional world through self-play, detect causal gaps, and recursively expand its rules with explicit approval. Use when the user wants to test a world's internal consistency, find undefined interactions, turn worldbuilding notes into a structured rule model, generate counterfactual scenarios, propose general mechanics, review a world's physics/society/economy, or grow a setting without overwriting canon. Also use for requests like "make this world more causally consistent", "what happens if...", "find holes in my magic system", "run a worldbuilding simulation", or "explore my world recursively".
---

# Recursive World Builder

Use this skill to test an existing fictional world and extend its causal rules.
The goal is **not** to write more lore. The goal is to find where the world
cannot answer a causal question, then propose the smallest reusable mechanism
that can — without silently changing canon.

## Non-negotiable rules

1. **Fiction outranks reality.** A world may have different gravity, time,
   biology, magic, or economics. Treat stated axioms as canon. Never "fix" an
   intentional deviation because it looks unrealistic.
2. **Exploration never changes canon.** Only an explicit user approval applies a
   proposal. Do not run `rwb approve` because a proposal looks good; ask first.
3. **Do not auto-approve.** The user can say "approve P-0001" explicitly. That is
   permission for that proposal only. Do not generalize it to others.
4. **Prefer one general mechanism over many exceptions.** If a finding is
   `undefined_interaction`, look for the family of cases it explains. A rule
   whose matcher names one demo object is a red flag.
5. **Do not restore retired canon.** `status: retired` facts and
   `status: deprecated` rules stay retired unless the user asks.
6. **Preserve artistic negative space.** Incompleteness is not automatically a
   bug. If a gap is better left mysterious, reject or defer the proposal.
7. **Label epistemics.** Deterministic simulation, host inference, and guesses
   are different things. Confidence values are subjective, not calibrated
   probabilities.
8. **Stay within budgets.** Never remove or bypass round/scenario/rule caps to
   "finish" a world.

## Setup

The skill assumes the package is installed (`pip install -e .`) or the checkout
is available. Resolve the wrapper relative to this skill directory:

```bash
RWB="python /path/to/recursive-world-builder/skills/recursive-world-builder/scripts/world_builder.py"
```

If the host has `rwb` on PATH, use `rwb` directly. Always operate on a specific
world directory (the one containing `world.json`), never on a repository root
that may contain unrelated private files.

## Core loop

```text
load world
  -> plan scenarios (deterministic probes + host-authored cases)
  -> simulate with declarative rules
  -> classify each observation
  -> deduplicate findings
  -> draft a general proposal (scripted or host-authored)
  -> show diffs, conflicts, and tests
  -> ASK FOR EXPLICIT APPROVAL
  -> apply + regression gate + snapshot
  -> re-run counterfactual tests
  -> report
  -> optionally explore again
```

## Start a world

If the user provides Markdown/JSON/YAML notes:

```bash
$RWB init ./my-world --title "My World"
$RWB validate ./my-world
$RWB summary ./my-world
```

`init` writes `world.json`, indexes source documents, and creates
`proposals.json`. Markdown supports a documented entity/location format and
embedded fenced JSON/YAML world fragments. Unstructured prose is preserved as
source material, not silently converted into rules. Read
`references/world-schema.md` when the user's notes need conversion.

If the world already exists, do not re-init. Validate and inspect it first.

## Explore

Offline deterministic mode (demo/CI only):

```bash
$RWB explore ./my-world --rounds 5 --focus physics
```

Host-reasoning mode (preferred for real settings):

```bash
$RWB explore ./my-world --rounds 5 --focus physics --architect host --json
```

Focus: `all`, `physics`, `biology`, `society`, `economy`, `character`.

In host mode, no proposal is generated. You must read the findings and author a
proposal. Before deciding, read:

- `my-world/world.json` (canon, rules, constraints);
- `my-world/exploration_cases.json` if present;
- the latest run JSON under `my-world/.rwb/runs/`;
- the relevant Markdown sources under `my-world/`.

### What the findings mean

- `explicit_violation` — the scenario breaks a declared constraint. This is an
  enforcement observation. Do not propose a patch to the constraint unless the
  user explicitly says the constraint is wrong.
- `undefined_interaction` — canon is silent. Candidate for a general mechanism.
- `allowed_but_unrealistic` — canon allows the outcome, reality does not. Keep
  canon. No proposal.
- `rule_conflict` — canon rules write the same state incompatibly. Surface the
  conflict; do not add another exception.

Read `references/causal-critique.md` for the full taxonomy.

## Author a proposal (host mode)

Write a JSON file with at least:

```json
{
  "title": "Generalized electrical conduction",
  "problem": "Contact with an energized conductor has no defined consequence.",
  "root_cause_hypothesis": "The world has no reusable electrical interaction layer.",
  "rationale": "One conduction cluster explains contact, insulation, water, and metal.",
  "expected_impacts": [
    "Insulation becomes a reusable material property.",
    "Water can become energized without a pool-specific rule."
  ],
  "generality": {
    "scope": "Any biological actor contacting any energized entity.",
    "special_case": false,
    "reusable": true
  },
  "confidence": 0.7,
  "rules": [
    {
      "id": "r_electric_contact_shock",
      "name": "Conductive contact injures biological actors",
      "description": "Biological actors without insulation are injured by energized targets.",
      "domain": "physics",
      "matcher": {
        "action_types": ["touch", "contact", "immerse"],
        "actor_tags_any": ["biological", "human", "animal"],
        "actor_tags_none": ["electrically_insulated"],
        "target_tags_any": ["energized"]
      },
      "effects": [
        {"kind": "modify_property", "target": "actor", "property": "health", "delta": -60},
        {"kind": "emit_event", "target": "actor", "event": "electric_shock"}
      ],
      "priority": 70,
      "status": "proposed",
      "depends_on": []
    }
  ],
  "test_plan": [
    {
      "id": "T-SHOCK-1",
      "title": "Mira touches the live line",
      "actor": "mira",
      "target": "power_line",
      "action": {"type": "touch"},
      "focus": "physics"
    }
  ]
}
```

Then:

```bash
$RWB propose ./my-world --file proposal.json
$RWB show ./my-world P-0001
```

Requirements:

- Every rule must carry an explicit id, matcher, effects, priority, and status.
- Every proposal must include a diff (computed automatically if omitted), at
  least one counterfactual test, expected impacts, and `generality.special_case`.
- `confidence` is subjective and must stay between 0 and 1. Never mark it
  calibrated.
- Dependencies must refer to canon rules or rules in the same proposal.
- Do not use a rule id that already exists unless you intend to **modify** it.
  In that case the diff becomes `action: "modify"` and the old version is kept
  in world history.

If `propose` reports conflicts, read them before asking for approval. Direct
conflicts require a separate `--accept-conflicts` decision.

## Review with the user

Show:

- finding type and evidence;
- the problem and root-cause hypothesis;
- affected systems;
- the rule diff (add/modify), dependencies, and conflicts;
- expected impacts;
- the counterfactual tests;
- explicit reminder that confidence is subjective.

Ask a direct question: **"Apply this proposal to canon?"** Do not act on a vague
"looks fine" if the user did not see the diff. Treat an explicit proposal id as
approval for that id only.

## Approve, reject, roll back

```bash
$RWB approve ./my-world P-0001 --yes
$RWB reject  ./my-world P-0001 --reason "too specific"
$RWB rollback ./my-world
```

Approval does all of the following atomically enough for a local tool:

1. blocks on direct conflicts unless overridden;
2. snapshots current canon;
3. applies add/modify/deprecate changes;
4. bumps `canon_version`;
5. runs the regression suite; on failure it restores the snapshot automatically;
6. re-runs the proposal's counterfactual tests;
7. writes a Markdown modification report.

After approval, read the report path and summarize:

- what changed;
- regression pass/fail;
- what the counterfactual tests now show;
- what remains undefined.

## Budgets and stopping

Defaults: 5 rounds, 24 scenarios, 8 new rules, 10 proposals, 2 consecutive
empty rounds. All are hard caps. Do not raise them without telling the user why.
Normal stop reasons include:

- `max_rounds`
- `max_scenarios`
- `max_new_rules`
- `max_proposals`
- `no_new_findings`
- `no_candidate_scenarios`

`no_candidate_scenarios` means the deterministic planner ran out of probes. It
does **not** mean the world is complete. A host agent can add scenarios to
`exploration_cases.json` and explore again.

## Continue recursively

After a patch, the same mechanism usually creates new legitimate questions.
Re-run exploration with the updated canon:

```bash
$RWB explore ./my-world --rounds 3 --focus physics --architect host --json
```

Examples of recursion: energized water, insulation failure, a vehicle hitting a
pole, a storm interacting with infrastructure, a law about who is liable for
damage. Stop when further findings are repetitions, low-value, or damage the
setting's artistic intent.

## Report template

Use this structure when reporting back:

```markdown
## World explored
[world id, canon version, focus, budgets]

## Deterministic observations
[what the engine actually simulated]

## Causal gaps
[gap type, evidence, affected systems]

## Proposal
[general mechanism, not a one-off; affected rules]

## Conflicts and dependencies
[direct/potential conflicts; dependency graph]

## Counterfactual tests
[scenario -> observed result after approval]

## Regression
[pass/fail and what stayed unchanged]

## Remaining uncertainty
[what is still undefined, what is host inference, what is a guess]
```

## References

Read only what you need:

- `references/world-schema.md` — world format, rules, constraints, canonical
  ingestion format.
- `references/causal-critique.md` — gap taxonomy, confidence semantics,
  deduplication, realism guardrails.
- `references/workflow.md` — full command workflow, proposal schema, approval
  and rollback rules, stop conditions.

## What not to do

- Do not invent rules during exploration and claim they are canon.
- Do not auto-approve or batch-approve proposals.
- Do not reinterpret a deliberate axiom as a bug.
- Do not turn every ambiguity into a rule.
- Do not claim "physics simulation", "formal verification", or "calibrated
  probability". The engine is a deterministic rule applier.
- Do not push private source material or API keys into a repository.
