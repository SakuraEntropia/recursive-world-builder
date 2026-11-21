# Recursive World Builder

**A bounded Agent Skill for recursive worldbuilding through self-play, causal-gap detection, and approval-gated rule expansion.**

[![CI](https://github.com/SakuraEntropia/recursive-world-builder/actions/workflows/ci.yml/badge.svg)](https://github.com/SakuraEntropia/recursive-world-builder/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Recursive World Builder lets a host agent enter a fictional world, probe it
with scenarios, find rule-level causal gaps, propose a reusable mechanism, and
apply it only after explicit approval. It is built for game settings, novels,
screenplays, TTRPG bibles, and original universes where internal consistency
matters but real-world physics does not.

It is **not** a physics engine, a market simulator, or a formal verifier. The
Python runtime stores state and executes declarative rules deterministically.
The host language model does the creative reasoning. Every output is labelled
as one of: deterministic simulation result, agent inference, or unverified
guess.

## 中文简介

Recursive World Builder 是一个可安装的 Agent Skill + Python 运行时：让 Agent
进入已有虚构世界，通过自演场景探测“因果缺口”，提出可复用的通用机制，并在用户
显式批准后递归扩展世界规则。

它不把 LLM 的合理回答伪装成物理仿真或形式验证。Python 只负责确定性的状态管理、
规则执行、冲突检测、回归门禁、快照回滚和测试记录；创意推理由宿主 Agent 完成。

三个关键区分：

- `undefined_interaction`：规则没定义，可能是值得补的机制；
- `explicit_violation`：违反既有约束，不自动改设定；
- `allowed_but_unrealistic`：设定允许，只是不符合现实直觉，**保留原创设定**。

任何新规则先进入 Proposal，永远不会在探索阶段自动写入 Canon。离线 Demo
`python scripts/run_demo.py --approve` 不依赖外部 LLM API，完整演示
“发现缺口 → 通用规则提案 → 显式批准 → 回归测试 → 反事实重测 → 修改报告”。

## The loop

```text
Existing world
    ↓
Generate scenario
    ↓
Agent self-play
    ↓
Observe consequences
    ↓
Detect causal gaps
    ↓
Propose general rules
    ↓
Run counterfactual tests
    ↓
Consistency / regression validation
    ↓
Explicit human approval
    ↓
Patch world model
    ↓
Repeat, within hard budgets
```

## Why this is different from a worldbuilding prompt

A normal generator invents more lore. This tool finds **where the existing
world cannot answer a causal question**, then asks for the smallest reusable
mechanism that answers a family of questions.

The demo starts with a live power line. Touching it has no defined consequence.
Instead of adding:

```text
if touching_power_line: die()
```

the proposal introduces general rules for:

- conductive contact and electrical injury;
- insulation as a material property;
- conductive media such as water becoming energized;
- vehicle impact damaging infrastructure.

The same mechanism then handles rubber boots, a line falling into a pool, a car
hitting a pole, and any future energized object. Counterfactual tests are
generated automatically and re-run after approval.

## Features

| Module | What it actually does |
| --- | --- |
| **World Model** | JSON/YAML world with entities, locations, properties, rules, constraints, relationships, canon facts, source documents, events, and a regression suite. Markdown ingestion understands a documented format and embedded JSON/YAML fences. |
| **Explorer Agent** | Deterministic probe planner for hazards, liquids, vehicles, institutions, markets, and character interactions. Host agents add in-character scenarios via `exploration_cases.json` or the Python API. |
| **Causal Critic** | Classifies `undefined_interaction`, `explicit_violation`, `allowed_but_unrealistic`, and `rule_conflict`. Confidence is explicitly subjective and uncalibrated. |
| **Rule Architect** | Produces diffs, dependencies, conflicts, expected impacts, counterfactual test plans, and general mechanism clusters. Prefers modifying an existing rule over duplicating one. |
| **Recursive Controller** | Hard caps on rounds, scenarios, proposals, and new rules; finding deduplication; finite stop conditions; snapshot rollback; regression gate; explicit approval. |
| **CLI + Skill** | `rwb` command with a real parser and a `SKILL.md` natural-language workflow. |

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Validate the demo world:

```bash
rwb validate examples/electric_city
rwb summary examples/electric_city
```

Run the complete offline demo on a temporary copy. No LLM API is required:

```bash
python scripts/run_demo.py --approve
```

The script copies the example into `demo-output/`, explores, drafts a proposal,
simulates the explicit approval step, applies the patch, runs the regression
gate, re-runs the counterfactual tests, and writes a modification report. The
committed example stays at canon v1.

### Demo output (abridged)

```text
[1] Bounded exploration (focus=physics, max_proposals=1)
    ran 7 scenarios; 2 findings; 1 proposal; stop=max_proposals

  Finding 1: undefined_interaction
    scenario:   Mira Vale probes Bellweather High-Voltage Line
    hypothesis: The world lacks a general electrical conduction/interaction
                mechanism...
    confidence: 0.92 (subjective; calibrated=False)

  Proposal P-0001: Generalized electrical conduction and infrastructure interaction
    rules: r_electric_contact_shock, r_electric_insulation_grounds,
           r_electric_medium_conduction, r_impact_infrastructure_damage

[4] Applying proposal and running the regression gate
    regression REG-WALK-1: PASS
    regression REG-COLLISION-1: PASS

[5] Counterfactual re-tests
    T-electricity-01: mira.health 100 -> 40
    T-electricity-02: insulation_grounds_current (no injury)
    T-electricity-03: pool_water tag energized
    T-electricity-04: mira.health 100 -> 40 in energized water
    T-electricity-05: pole.integrity 100 -> 75

[6] canon v2; rules: 2 -> 6
```

See [`docs/demo.md`](docs/demo.md) for the full captured run.

## CLI

```bash
rwb init ./my-world                    # Markdown/JSON/YAML -> world.json
rwb validate ./my-world
rwb explore ./my-world --rounds 5 --focus physics
rwb explore ./my-world --focus society --architect host --json
rwb proposals ./my-world
rwb show ./my-world P-0001
rwb approve ./my-world P-0001          # prompts unless --yes
rwb reject ./my-world P-0001 --reason "too specific"
rwb propose ./my-world --file proposal.json
rwb regressions ./my-world
rwb rollback ./my-world
rwb sources ./my-world
```

Focus values: `all`, `physics`, `biology`, `society`, `economy`, `character`.

### Two architect modes

- `--architect scripted` — deterministic mechanism templates. Fast, testable,
  offline. Useful for demos and CI. Proposals are explicitly labelled
  `scripted_mechanism_template`.
- `--architect host` — exploration only. The host agent reads findings and
  writes its own proposal JSON, then calls `rwb propose`. This is the mode to
  use for serious worldbuilding, unusual physics, or domains where a generic
  template would be wrong.

## Agent Skill

The skill lives at [`skills/recursive-world-builder/SKILL.md`](skills/recursive-world-builder/SKILL.md).
Install it the way your host discovers Agent Skills, for example:

```bash
mkdir -p ~/.agents/skills
ln -s "$(pwd)/skills/recursive-world-builder" \
      ~/.agents/skills/recursive-world-builder
```

Then ask naturally:

```text
/recursive-world-builder init ./my-world
/recursive-world-builder explore --rounds 5 --focus physics
/recursive-world-builder proposals
/recursive-world-builder approve P-0001
```

Natural-language requests are mapped by the host to the real CLI. The skill
bundle includes:

```text
skills/recursive-world-builder/
├── SKILL.md
├── references/
│   ├── world-schema.md
│   ├── causal-critique.md
│   └── workflow.md
└── scripts/world_builder.py
```

The wrapper executes the installed package, or the checkout's `src/` directory.

## Host-authored proposals

For creative worlds, the intended flow is:

```bash
rwb explore ./my-world --focus physics --architect host --json > gaps.json
# The agent reads my-world/world.json and gaps.json, then writes proposal.json.
rwb propose ./my-world --file proposal.json
rwb show ./my-world P-0001
rwb approve ./my-world P-0001
```

A proposal must include:

- **problem** — what the world failed to answer;
- **root-cause hypothesis** — why the gap exists;
- **proposed rules** — preferably a general mechanism cluster;
- **expected impacts** — what becomes explainable;
- **potential conflicts** — detected automatically, reviewed by the author;
- **counterfactual test plan** — scenarios to re-run after applying;
- **dependencies and diff** — how it composes with existing canon.

See [`references/workflow.md`](skills/recursive-world-builder/references/workflow.md)
for a minimal proposal example.

## The three critical distinctions

| Classification | Meaning | Default action |
| --- | --- | --- |
| `explicit_violation` | The scenario contradicts a declared constraint. | Do **not** patch canon; treat it as an enforcement observation. |
| `undefined_interaction` | Canon is silent. A reusable mechanism may be missing. | Propose a general rule for review. |
| `allowed_but_unrealistic` | Canon defines the outcome, but it differs from real-world intuition. | **Preserve canon.** Fictional axioms win. |

`undefined` is not automatically a defect either. Sometimes the right answer is
deliberate narrative negative space. The controller can stop, and a human can
reject the proposal.

## World model

```jsonc
{
  "world_id": "electric_city",
  "canon_version": 1,
  "entities": { "mira": { "type": "character", "tags": ["human"], "properties": {"health": 100} } },
  "locations": { "street": { "tags": ["outdoor"] } },
  "rules": {
    "r_shock": {
      "matcher": { "action_types": ["touch"], "target_tags_any": ["energized"] },
      "effects": [
        { "kind": "modify_property", "target": "actor", "property": "health", "delta": -60 }
      ],
      "depends_on": [],
      "status": "canon"
    }
  },
  "constraints": {},
  "canon": [],
  "regression_suite": []
}
```

Rule effects are deliberately small: `set_property`, `modify_property`,
`add_tag`, `remove_tag`, `emit_event`, `move_entity`. Conditions support tags
and property comparisons. There is no hidden physics.

Full schema: [`references/world-schema.md`](skills/recursive-world-builder/references/world-schema.md).

## Safety and canon rules

- Exploration **never** writes a proposal into canon.
- Approval is a separate explicit operation; CLI approval prompts unless `--yes`.
- A rejected proposal leaves `world.json` byte-for-byte equivalent (aside from
  proposals storage).
- Direct rule conflicts block application unless `--accept-conflicts` is passed.
- Every approval creates a pre-apply snapshot.
- A failed regression gate restores the snapshot automatically.
- Retired canon is never silently restored.
- No API keys, tokens, or private world data are required or transmitted.

## Project layout

```text
.
├── src/recursive_world_builder/
│   ├── model.py       # dataclasses, validation, serialization
│   ├── engine.py      # deterministic rule application
│   ├── explorer.py    # probe planner and scenario execution
│   ├── critic.py      # structured causal findings
│   ├── mechanisms.py  # scripted mechanism templates
│   ├── architect.py   # proposal diffs, conflicts, application
│   ├── controller.py  # budgets, approval, regression, rollback
│   ├── storage.py     # atomic JSON, proposals, snapshots, runs
│   ├── ingest.py      # Markdown/JSON/YAML ingestion
│   ├── reporting.py   # Markdown reports
│   └── cli.py         # rwb
├── skills/recursive-world-builder/
├── examples/electric_city/
├── examples/weird_physics/
├── tests/
└── docs/
```

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m ruff format --check src tests
```

Tests cover world loading, undefined-gap detection, structured proposals,
direct conflicts, rejection immutability, approval, stopping, regression
preservation, rollback on regression failure, Markdown/YAML ingestion, and the
CLI. See [`docs/development.md`](docs/development.md).

## Limitations

- No continuous physics, fluid dynamics, economy clearing, or social simulation.
- Rule effects are declarative and discrete; magnitude is hand-authored, not derived.
- The scripted architect is a template library, not a reasoning model.
- LLM-authored proposals can be wrong, inconsistent, or over-specific. Review them.
- Automatic probes are shallow; deep roleplay and scenario invention belong to the host agent.
- Regression fingerprints prove deterministic *unchanged behavior*, not artistic quality.
- No multi-agent negotiation, no formal proof, no calibrated probabilities.
- YAML support requires the optional `PyYAML` dependency.

See [`docs/limitations.md`](docs/limitations.md) for details and the roadmap.

## License

MIT. See [LICENSE](LICENSE).
