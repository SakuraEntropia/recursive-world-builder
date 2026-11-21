# Examples

## `electric_city/`

The main acceptance demo. A live power line has no defined electrical
consequences. Exploration finds the gap, a general mechanism cluster is
proposed, the user approves it, and counterfactual tests exercise contact,
insulation, water, and vehicle impact.

```bash
python scripts/run_demo.py --approve
```

## `weird_physics/`

A setting whose gravity deliberately differs from Earth. It demonstrates the
`allowed_but_unrealistic` classification: the critic records the real-world
expectation but preserves the fictional axiom and creates no proposal.

```bash
rwb explore examples/weird_physics --focus physics --architect host
```

Both examples are deliberately small. They test behavior, not production-scale
worlds.
