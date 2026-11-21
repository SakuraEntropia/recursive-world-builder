# Offline Demo — Actual Run

Captured from the deterministic demo. No external LLM API is used. The
`--approve` flag makes the script perform the explicit approval step that a
human would otherwise perform; the library still requires a separate
`RecursiveController.approve()` call.

```bash
python scripts/run_demo.py --approve
```

```text
==============================================================================
Recursive World Builder — offline electric_city demo
==============================================================================
World: Electric City — The Live Wire (electric_city), canon v1
Entities: 9, rules: 2
Working copy: demo-output/electric_city

[1] Bounded exploration (focus=physics, max_proposals=1)
    ran 7 scenarios; 2 findings; 1 proposal; stop=max_proposals

  Finding 1: undefined_interaction
    scenario:   Mira Vale probes Bellweather High-Voltage Line
    observation:no canonical rule defines a consequence for this interaction
    hypothesis: The world lacks a general electrical conduction/interaction mechanism. This is a missing reusable rule, not merely a missing one-off consequence for this object.
    systems:    electricity, materials, health, biology
    confidence: 0.92 (subjective; calibrated=False)

  Finding 2: undefined_interaction
    scenario:   Delivery Car collides with Bellweather Utility Pole
    observation:no canonical rule defines a consequence for this interaction
    hypothesis: The world lacks a general impact/damage mechanism linking moving objects, structures, and downstream hazards.
    systems:    kinetics, materials, infrastructure
    confidence: 0.92 (subjective; calibrated=False)

  Proposal P-0001: Generalized electrical conduction and infrastructure interaction
    problem:   no canonical rule defines a consequence for this interaction
    root cause:The world lacks a general electrical conduction/interaction mechanism. This is a missing reusable rule, not merely a missing one-off consequence for this object.
    rules:     r_electric_contact_shock, r_electric_insulation_grounds, r_electric_medium_conduction, r_impact_infrastructure_damage
    conflicts: 0
    tests:     T-electricity-01, T-electricity-02, T-electricity-03, T-electricity-04, T-electricity-05
    expected impacts:
      - Biological contact with any energized entity has a defined injury result.
      - Electrical insulation is represented as a reusable material property.
      - Water, wet ground, and metal debris can become energized through one rule.
      - Infrastructure impact becomes a source of downstream hazards rather than a dead end.

[2] Canon before approval
    canon_version=1; rules=2
    (No proposal content is in canon yet.)

[3] Approval
    DEMO: --approve was passed, so the script performs the explicit approval
    step that a human would otherwise perform. The library API still requires
    a separate approve() call; exploration never applies proposals itself.

[4] Applying proposal and running the regression gate
    applied=True; world v2
    Proposal applied. Canon is now v2; 4 rule(s) changed.
    regression REG-WALK-1: PASS (event walked)
    regression REG-COLLISION-1: PASS (crate.integrity 50 -> 30; crate tag damaged; event cargo_crushed)

[5] Counterfactual re-tests
    T-electricity-01: Mira Vale touches Bellweather High-Voltage Line
      -> mira.health 100 -> 40; mira tag electrically_shocked; event electric_shock
    T-electricity-02: Mira Vale touches Bellweather High-Voltage Line while insulated
      -> event insulation_grounds_current
    T-electricity-03: Bellweather High-Voltage Line energizes a conductive medium
      -> pool_water tag energized; event medium_energized
    T-electricity-04: Mira Vale enters energized water
      -> mira.health 100 -> 40; mira tag electrically_shocked; event electric_shock
    T-electricity-05: A vehicle strikes Bellweather Utility Pole
      -> pole.integrity 100 -> 75; pole tag damaged; event infrastructure_impact

[6] Result
    canon v2; rules: 2 -> 6
    report: demo-output/electric_city/reports/rule-change-P-0001-v2.md
    run report: demo-output/electric_city/.rwb/runs/latest.json

Done. Source example remains at canon v1; only the working copy changed.
```

## Full check

```text
$ bash scripts/check.sh
All checks passed!
42 passed in 0.19s
example canon v1 intact
```

## Why this matters

- The gap was discovered from the world's silence, not from an expected-answer
  fixture.
- The proposal is a mechanism cluster, not a `power_line` special case.
- Canon did not change during exploration.
- Approval advanced canon from v1 to v2.
- Unrelated regression cases stayed green.
- Five counterfactual tests were re-executed against the patched world.
- The committed example remains at canon v1; this run used a disposable copy.
