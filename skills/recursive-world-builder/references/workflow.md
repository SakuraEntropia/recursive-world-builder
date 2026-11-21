# Workflow

## 0. Decide the world directory

A world is a directory containing `world.json` plus optional source material:

```text
my-world/
├── world.json
├── proposals.json          # created automatically
├── regressions.json        # created at first approval or by regressions --update
├── exploration_cases.json  # optional host-authored scenarios
├── .rwb/                   # runs and snapshots, git-ignored
├── reports/                # Markdown reports, git-ignored
└── source/                 # Markdown / JSON / YAML reference material
```

Never run commands against a directory that also contains unrelated private
documents. `init` writes into the directory you name.

## 1. Initialize or validate

```bash
rwb init ./my-world --title "My World"
rwb validate ./my-world
rwb summary ./my-world
```

`init` behavior:

- if `world.json` exists, load and validate it;
- otherwise scan Markdown/JSON/YAML;
- parse documented Markdown entities/locations and fenced JSON/YAML fragments;
- index every source with path, SHA-256, outline, and excerpt;
- write `world.json` and an empty `proposals.json`.

Use `--force` only to rebuild from source material. It resets proposals and
regressions and can discard canon changes; confirm with the user first.

## 2. Add host-authored scenarios

The deterministic planner only knows general semantic families. Add fictional,
in-character, or world-specific probes in `exploration_cases.json`:

```json
{
  "scenarios": [
    {
      "id": "EXT-1",
      "title": "The archivist reads a forbidden ledger",
      "actor": "archivist",
      "target": "ledger",
      "action": {"type": "read", "tags": ["knowledge", "taboo"]},
      "description": "Test whether forbidden knowledge has a defined consequence.",
      "focus": "character",
      "tags": ["external", "boundary"],
      "source": "host-authored"
    }
  ]
}
```

External scenarios run before generated probes for the selected focus. They are
inputs, never expected answers.

## 3. Explore

```bash
# deterministic, offline, template-backed
rwb explore ./my-world --rounds 5 --focus physics

# host reasoning: findings only
rwb explore ./my-world --rounds 5 --focus all --architect host --json
```

Budgets:

| Flag | Default | Meaning |
| --- | ---: | --- |
| `--rounds` | 5 | Maximum recursive rounds. |
| `--max-scenarios` | 24 | Maximum scenarios executed in one run. |
| `--max-new-rules` | 8 | Maximum proposed new rules in one run. |
| `--max-proposals` | 10 | Maximum proposals created in one run. |
| `--max-empty-rounds` | 2 | Stop after this many consecutive rounds with no new findings. |

Stop reasons: `max_rounds`, `max_scenarios`, `max_new_rules`, `max_proposals`,
`no_new_findings`, `no_candidate_scenarios`. None of these means "world
complete".

Outputs:

- `my-world/.rwb/runs/run-*.json` — machine-readable run;
- `my-world/reports/run-*.md` — human report;
- `my-world/proposals.json` — pending proposals (scripted mode only).

## 4. Review findings

For each finding, inspect:

- `gap_type`;
- `observation` (what rules actually did);
- `hypothesis`;
- `affected_systems`;
- `confidence` and `calibrated` (always false);
- `dedupe_key`;
- the original scenario.

Classify:

- violation -> do not patch the constraint;
- undefined -> candidate mechanism;
- allowed but unrealistic -> preserve;
- rule conflict -> resolve existing overlap, do not add an exception.

If a finding is low value, stop. Not every silence needs a rule.

## 5. Author a proposal (host mode)

```bash
rwb explore ./my-world --architect host --json > /tmp/gaps.json
$EDITOR proposal.json
rwb propose ./my-world --file proposal.json
```

A proposal must be reviewable without reading the agent's private thoughts.
Minimum shape:

```json
{
  "title": "Generalized electrical conduction",
  "problem": "Contact with an energized conductor has no defined consequence.",
  "root_cause_hypothesis": "No reusable electrical interaction layer exists.",
  "rationale": "One cluster covers contact, insulation, media, and metal.",
  "expected_impacts": [
    "Insulation becomes a reusable material property.",
    "Energized water composes with the shock rule."
  ],
  "generality": {
    "scope": "Any biological actor and any energized target.",
    "special_case": false,
    "reusable": true
  },
  "confidence": 0.7,
  "rules": [
    {
      "id": "r_electric_contact_shock",
      "name": "Conductive contact injures biological actors",
      "description": "Unprotected biological actors are injured by energized targets.",
      "domain": "physics",
      "matcher": {
        "action_types": ["touch", "contact", "immerse"],
        "actor_tags_any": ["human", "biological", "animal"],
        "actor_tags_none": ["electrically_insulated"],
        "target_tags_any": ["energized"]
      },
      "effects": [
        {"kind": "modify_property", "target": "actor", "property": "health", "delta": -60},
        {"kind": "add_tag", "target": "actor", "tag": "electrically_shocked"},
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

`rule_changes` is computed automatically if omitted. To modify an existing rule,
reuse its id; the diff becomes `action: "modify"` and both versions are retained
in `history`.

### Generality checklist

- Does one rule explain multiple probes?
- Are target tags semantic (`energized`, `fragile`) rather than demo IDs?
- Is there an existing rule to amend before adding a new one?
- Are dependencies explicit?
- Are counterfactual tests able to falsify the proposal?
- Is `special_case` genuinely justified?

## 6. Review conflicts and dependencies

`rwb show ./my-world P-0001` prints the full JSON. Look for:

- `direct` conflicts: incompatible writes, duplicate ids, declared conflicts;
- `potential` conflicts: overlapping prohibitions, redundant matchers,
  set/modify overlap;
- missing dependencies;
- stale `world_version`.

Resolve before approval. Do not use `--accept-conflicts` to bypass a conflict
the user has not seen.

## 7. Ask for approval

Present the problem, hypothesis, diff, conflicts, impacts, and test plan. Ask:
**"Apply this proposal to canon?"**

Only after an explicit yes:

```bash
rwb approve ./my-world P-0001 --yes
```

Without `--yes`, the CLI prompts. In an agent session, confirmation is a user
message, not an internal decision.

## 8. What approval does

1. Re-detects conflicts against current canon.
2. Checks proposal world version.
3. Snapshots current canon under `.rwb/snapshots/`.
4. Applies add/modify changes.
5. Marks superseded rules deprecated.
6. Increments `canon_version` and appends `history`.
7. Runs regression cases against the new canon.
8. On regression failure, restores the snapshot and marks the proposal
   `regression_failed`.
9. Re-runs the proposal's counterfactual tests.
10. Writes `reports/rule-change-<id>-v<version>.md`.

A rejected proposal:

```bash
rwb reject ./my-world P-0001 --reason "too specific"
```

does not change `world.json`.

## 9. Regression gate

At first approval, the controller seeds `regressions.json` from
`world.regression_suite`. Every approval re-runs those cases and compares
fingerprints.

If a canon change *intentionally* changes a regression outcome, do not bypass
the gate silently. Review and update the baseline deliberately:

```bash
rwb regressions ./my-world --update
```

This is a canon-adjacent decision. Tell the user.

## 10. Rollback

```bash
rwb rollback ./my-world                    # latest snapshot
rwb rollback ./my-world --snapshot FILE    # specific snapshot
```

Snapshots are written before every approval attempt. Rollback restores canon;
proposal status is not rewritten by the CLI rollback command.

## 11. Re-explore

After a patch, new mechanisms create new legitimate questions. Run exploration
again. Prefer host mode. Look for composition gaps (water + electricity,
insulation failure, infrastructure damage + law, storm + grid), not repetitions
of the same finding.

Stop when:

- budgets are reached;
- findings repeat;
- proposals would be low-leverage lore;
- the setting's mystery or artistic space would be damaged;
- the user is satisfied.

## 12. Error handling

| Symptom | Meaning | Action |
| --- | --- | --- |
| `StaleProposalError` | Canon changed after proposal creation. | Re-run exploration or rebase the proposal. Do not force apply. |
| `ProposalConflictError` | Direct conflict with current canon. | Surface it; resolve or ask for explicit override. |
| `regression_failed` | A previously stable behavior changed. | Inspect report; update baseline only deliberately. |
| `No candidate scenarios` | Deterministic planner exhausted probes. | Add host scenarios or conclude. |
| YAML import error | Optional dependency missing. | `pip install 'recursive-world-builder[yaml]'` |

## 13. Epistemic labels in reports

- **Deterministic observation** — produced by `RuleEngine` from canon rules.
- **Agent inference** — the critic's hypothesis and confidence.
- **Proposal** — unverified, not canon, awaiting review.
- **Applied canon** — explicitly approved and regression-gated.
- **Unverified guess** — anything else; label it as such.

Never write "simulation proves" or "calibrated confidence" for any of these.
