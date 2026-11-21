# Python API

The CLI is a thin wrapper around the same library. Import from
`recursive_world_builder`.

## Load and validate

```python
from recursive_world_builder import WorldStore

store = WorldStore("examples/electric_city")
world = store.load_world()
assert world.world_id == "electric_city"
world.assert_valid()
```

## Simulate one scenario

```python
from recursive_world_builder import Action, RuleEngine, Scenario

scenario = Scenario(
    id="probe-1",
    title="Mira touches the live line",
    actor="mira",
    target="power_line",
    action=Action("touch", tags=["contact"]),
)
observation = RuleEngine().simulate(world, scenario)
print(observation.summary())
```

`simulate` works on a private clone. Neither canon nor the caller's `World`
object is mutated, even when an effect names an explicit entity id.

## Explore and critique

```python
from recursive_world_builder import CausalCritic, Explorer

explorer = Explorer(external_path="examples/electric_city/exploration_cases.json")
for scenario, observation in explorer.discover(world, focus="physics", limit=4):
    finding = CausalCritic().analyze(world, scenario, observation)
    if finding:
        print(finding.gap_type, finding.scenario)
```

## Build a scripted proposal

```python
from recursive_world_builder import RuleArchitect

architect = RuleArchitect()
proposal = architect.build_proposal(
    world,
    finding,
    scenario,
    proposal_id=store.next_proposal_id(),
    existing_proposals=store.load_proposals(),
)
if proposal:
    store.upsert_proposal(proposal)
```

The scripted route is for demos and tests. For host reasoning, use
`architect.ingest_external_proposal(world, payload, proposal_id=...)` with a
proposal dictionary.

## Approve and apply

```python
from recursive_world_builder import RecursiveController

controller = RecursiveController(store)
approval = controller.approve(proposal.id)
print(approval.applied, approval.world_version)
print(approval.regression_results)
print(approval.post_tests)
```

Approval performs the conflict check, snapshot, application, regression gate,
rollback on regression failure, counterfactual re-tests, and report writing.

## Explore within budgets

```python
result = controller.explore(
    focus="physics",
    max_rounds=3,
    max_scenarios=12,
    max_new_rules=6,
    max_proposals=4,
)
print(result.stop_reason)
print(len(result.findings), len(result.proposals))
```

## Reject and roll back

```python
controller.reject(proposal.id, reason="too specific")
restored = controller.rollback()  # latest snapshot
```

## Load YAML

YAML support is optional:

```bash
python -m pip install -e ".[yaml]"
```

`ingest_directory` accepts `.yaml`/`.yml`; the canonical stored form remains
`world.json`.

## Public exports

`World`, `WorldStore`, `RuleEngine`, `Explorer`, `ScenarioGenerator`,
`CausalCritic`, `RuleArchitect`, `RecursiveController`, `Proposal`,
`GapFinding`, `RunLimits`, `RunResult`, `ApprovalResult`,
`ProposalConflictError`, `StaleProposalError`, `ProposalStateError`,
`StorageError`, `ValidationError`, `ingest_directory`, `init_world`.

See the type hints and docstrings in `src/recursive_world_builder/` for exact
signatures.
