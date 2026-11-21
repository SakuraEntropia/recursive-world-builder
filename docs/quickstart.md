# Quickstart

## Install

```bash
git clone https://github.com/SakuraEntropia/recursive-world-builder.git
cd recursive-world-builder
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Python 3.11+ is required. YAML support is optional:

```bash
python -m pip install -e ".[yaml]"
```

## Run the demo

```bash
rwb validate examples/electric_city
rwb summary examples/electric_city
python scripts/run_demo.py --approve
```

The demo runs entirely offline. It copies the world to `demo-output/` so the
committed example stays at canon v1.

What happens:

1. deterministic probes find that touching the live line has no defined effect;
2. the scripted architect proposes four general rules;
3. the demo calls the explicit approval API;
4. canon advances to v2;
5. unrelated walking/collision regressions still pass;
6. five counterfactual tests re-run;
7. a modification report is written.

Inspect:

```bash
cat demo-output/electric_city/reports/rule-change-P-0001-v2.md
python -m json.tool demo-output/electric_city/.rwb/runs/latest.json | head
```

## Create your own world

Option A — structured JSON already exists:

```bash
mkdir my-world
cp my-world.json my-world/world.json
rwb validate my-world
```

Option B — Markdown notes:

```markdown
# The Salt Republic

## Entities

### ada — Ada of the Dunes
- type: character
- location: market
- tags: human, alive, biological, actor
- properties: health=100, wealth=3

### salt — Salt Reserve
- type: object
- location: market
- tags: resource, market, commodity
- properties: stock=500, price=2

## Locations

### market — Salt Market
- tags: outdoor, public, market
- properties: crowded=true

## Canon

- Salt is the only recognized currency.
```

```bash
rwb init my-world --title "The Salt Republic"
rwb validate my-world
```

The Markdown parser recognizes the documented entity/location shape and fenced
JSON/YAML fragments. Everything else is indexed as source material for the host
agent.

## Explore

```bash
# deterministic templates
rwb explore my-world --rounds 3 --focus all

# host reasoning
rwb explore my-world --rounds 3 --focus economy --architect host --json
```

Focus is one of `all`, `physics`, `biology`, `society`, `economy`, `character`.

Generated artifacts:

- `my-world/reports/run-<id>.md`
- `my-world/.rwb/runs/<id>.json`
- proposals in scripted mode

## Review a proposal

```bash
rwb proposals my-world
rwb show my-world P-0001
```

Check:

- `gap_type` and evidence;
- rule diff and dependencies;
- direct/potential conflicts;
- expected impacts;
- counterfactual test plan;
- `confidence_kind` and `calibrated`.

## Approve or reject

```bash
rwb approve my-world P-0001          # interactive prompt
rwb approve my-world P-0001 --yes    # explicit automation
rwb reject  my-world P-0001 --reason "too specific"
rwb rollback my-world
```

Approval is gated by:

1. explicit confirmation;
2. world-version freshness;
3. direct-conflict check;
4. regression suite;
5. snapshot rollback if a regression fails.

## Host-authored proposals

```bash
rwb explore my-world --focus physics --architect host --json > gaps.json
```

Read `my-world/world.json`, the source documents, and `gaps.json`. Write a
proposal JSON (see the skill's `references/workflow.md`), then:

```bash
rwb propose my-world --file proposal.json
rwb show my-world P-0001
```

The tool computes the rule diff if omitted and detects conflicts automatically.

## Inspect canon

```bash
rwb summary my-world
rwb sources my-world
rwb regressions my-world
```

`world.json` is the source of truth. `.rwb/` and `reports/` are runtime
artifacts and should stay out of version control unless you deliberately want to
archive a run.

## Next steps

- Read [`architecture.md`](architecture.md) for internals.
- Read [`limitations.md`](limitations.md) before claiming simulation fidelity.
- Read the skill:
  [`SKILL.md`](../skills/recursive-world-builder/SKILL.md).
