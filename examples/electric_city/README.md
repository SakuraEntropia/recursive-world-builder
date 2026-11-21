# Electric City demo

This example intentionally contains a single conspicuous causal gap: nobody has
defined what electricity does to people, water, or infrastructure.

## Load the world

```bash
rwb validate examples/electric_city
rwb summary examples/electric_city
```

## Run the bounded loop

```bash
rwb explore examples/electric_city --rounds 3 --focus physics --max-proposals 1
rwb proposals examples/electric_city
rwb show examples/electric_city P-0001
```

The default `--architect scripted` mode uses deterministic mechanism templates
so the demo runs without any LLM API. A real host agent should use
`--architect host` and author a proposal with `rwb propose` instead.

## Approve explicitly

```bash
rwb approve examples/electric_city P-0001 --yes
```

Approval applies the rule cluster, bumps `canon_version`, runs the regression
suite, re-runs the counterfactual tests, and writes
`reports/rule-change-P-0001-v2.md`.

## Run a reproducible demo on a temporary copy

```bash
python scripts/run_demo.py --approve
```

This leaves the committed example world at canon v1. Artifacts are written to
`demo-output/`, which is git-ignored.

## What to look for

- A finding with `gap_type: undefined_interaction`.
- A proposal with four *general* rules: shock, insulation, medium conduction,
  and infrastructure impact — not an object-specific `if power_line: die()`.
- A counterfactual test plan that includes a person, water, boots, and a car.
- Regression cases stay green because unrelated walking and crate-collision
  outcomes do not change.
- Canon changes only after approval; rejection leaves `world.json` untouched.
