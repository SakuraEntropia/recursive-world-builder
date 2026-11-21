# The Slow-Fall Plateau

A deliberately non-Earthlike world used to test the epistemic guardrail.

The plateau's gravity is one-tenth of Earth standard. A coin dropped from a
height drifts slowly. A naive realism checker would call this a bug; this
project classifies it as:

```text
gap_type: allowed_but_unrealistic
recommended_action: preserve_canon
```

Run it:

```bash
rwb explore examples/weird_physics --rounds 2 --focus physics --architect host
```

No proposal is created. The finding records the real-world expectation only as
a comparison, not as authority over the setting.

This is the difference between:

- **undefined** — canon is silent, so a reusable mechanism may be missing;
- **violation** — the scenario contradicts a declared constraint;
- **allowed but unrealistic** — canon defines the outcome, and the fiction wins.
