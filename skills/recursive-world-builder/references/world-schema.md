# World Model Schema

The canonical on-disk file is `world.json` (UTF-8, pretty-printed). YAML input
is accepted by ingestion, but committed canon is JSON so it reviews cleanly in a
diff.

Schema version: **1.0**. The major version must match.

## Top level

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | string | recommended | `"1.0"`; mismatched major version is rejected. |
| `world_id` | string | yes | Stable machine id (snake_case or kebab-case). |
| `title` | string | yes | Human title. |
| `description` | string | no | Short premise. |
| `canon_version` | integer | yes | Starts at 1; incremented once per approved proposal. |
| `entities` | object or list | no | Keyed by entity id, or list with ids. |
| `locations` | object or list | no | Keyed by location id. |
| `relationships` | object or list | no | Typed links between entities. |
| `rules` | object or list | no | Canon rules. Proposal rules live in `proposals.json`. |
| `constraints` | object or list | no | Axioms, prohibitions, invariants. |
| `canon` | list | no | Established facts. |
| `events` | list | no | Persistent canonical event log; scenario events are ephemeral. |
| `regression_suite` | list of scenarios | no | Scenarios whose deterministic outcome must not change unexpectedly. |
| `source_documents` | list | no | Indexed Markdown/JSON/YAML sources with path, digest, outline, excerpt. |
| `settings` | object | no | Free-form metadata, genre, reality profile. |
| `history` | list | no | Versioned rule-change history written by the controller. |

## Entity

```json
{
  "id": "mira",
  "name": "Mira Vale",
  "type": "character",
  "location_id": "street",
  "tags": ["human", "alive", "biological", "actor"],
  "properties": {"health": 100, "alive": true},
  "description": "A courier."
}
```

`type` is open-ended (`character`, `object`, `vehicle`, `institution`,
`creature`, ...). Tags drive matching more often than types. Properties are
plain JSON values and support numeric comparisons in rule conditions.

`location_id`, when present, must reference a declared location.

## Location

```json
{
  "id": "street",
  "name": "Bellweather Street",
  "tags": ["outdoor", "urban", "public"],
  "properties": {"wet": false},
  "description": "A narrow street."
}
```

Locations support tags and properties too. A scenario's location is inferred
from the actor's `location_id`; rule matchers can constrain location tags.

## Relationship

```json
{
  "id": "rel-pole-supports-line",
  "source_id": "pole",
  "target_id": "power_line",
  "kind": "supports",
  "properties": {}
}
```

Relationships are validated for referential integrity but the current rule
engine does not traverse them automatically. They are context for the host
agent and for future rule extensions.

## Canon fact

```json
{
  "id": "CF-001",
  "statement": "The high-voltage line is always energized.",
  "status": "canon",
  "source": "source/electric_city.md"
}
```

`status` is `canon` or `retired`. Retired facts are never silently restored.
String entries are accepted at ingestion time and receive `CF-###` ids.

## Constraint

```json
{
  "id": "C-SUBSTATION-1",
  "kind": "prohibition",
  "severity": "hard",
  "description": "Residents may not enter the substation.",
  "message": "The substation is a prohibited area.",
  "matcher": {
    "action_types": ["enter", "sabotage"],
    "target_tags_any": ["substation"]
  },
  "source": "source/electric_city.md"
}
```

Kinds:

- `axiom` — declarative truth for the host agent. The deterministic engine does
  not evaluate free-form axioms.
- `prohibition` — an action matching the matcher is blocked and classified as
  `explicit_violation`.
- `invariant` — currently evaluated like a prohibition when a matcher is
  supplied; future versions may add post-state checks.

Severity is `hard` or `soft`. Both block deterministic simulation when matched;
the distinction is preserved for reporting and host judgement.

## Rule

```json
{
  "id": "r_electric_contact_shock",
  "name": "Conductive contact injures biological actors",
  "description": "Energized targets injure unprotected biological actors.",
  "domain": "physics",
  "matcher": {
    "action_types": ["touch", "contact", "immerse"],
    "actor_tags_any": ["human", "biological", "animal"],
    "actor_tags_none": ["electrically_insulated"],
    "target_tags_any": ["energized"],
    "target_tags_none": [],
    "location_tags_any": [],
    "actor_properties": [],
    "target_properties": [{"key": "voltage", "op": "gte", "value": 50}],
    "location_properties": []
  },
  "effects": [
    {"kind": "modify_property", "target": "actor", "property": "health", "delta": -60},
    {"kind": "add_tag", "target": "actor", "tag": "electrically_shocked"},
    {"kind": "emit_event", "target": "actor", "event": "electric_shock"}
  ],
  "priority": 70,
  "status": "canon",
  "version": 1,
  "depends_on": [],
  "conflicts_with": [],
  "supersedes": [],
  "tags": ["electricity", "injury"],
  "defies_real_world_expectation": false,
  "rationale": "Reusable conduction mechanism.",
  "provenance": {"proposal_id": "P-0001"}
}
```

Domains: `physics`, `biology`, `society`, `economy`, `character`, `general`.

Status in canon: `canon` or `deprecated`. Proposal rules must be `proposed`.

Priorities: higher runs first. A `set_property` takes ownership of a
target/property; a later write to that property is suppressed and recorded in
`suppressed_rule_ids` (the critic treats this as a `rule_conflict`). Compatible
`modify_property` effects may stack when no `set_property` owns the property.

`depends_on` must reference canon rules or rules in the same proposal. This is a
consistency check, not an execution scheduler.

`defies_real_world_expectation` marks an intentional fictional deviation. If a
scenario also carries a real-world expectation and `reality_check` tag, the
critic classifies the outcome as `allowed_but_unrealistic` rather than a gap.

### Matcher semantics

- `action_types`: one of these action types must match.
- `*_tags_any`: empty means "any"; otherwise at least one tag must match.
- `*_tags_none`: none of these tags may be present.
- Property conditions: `eq`, `ne`, `exists`, `truthy`, `gt`, `gte`, `lt`, `lte`,
  `in`, `contains`.
- Actor, target, and location are optional; target conditions on a scenario
  without a target cannot match.

### Effect kinds

| Kind | Required | Behavior |
| --- | --- | --- |
| `set_property` | `property`, non-null `value` | Overwrite a property. |
| `modify_property` | `property`, numeric `delta` | Add to current numeric value. |
| `add_tag` | `tag` | Append if absent. |
| `remove_tag` | `tag` | Remove if present. |
| `emit_event` | `event` or `message` | Record an ephemeral scenario event. |
| `move_entity` | `property` or `value` destination | Change an entity's `location_id`. |

`target` is `actor`, `target`, `location`, or an explicit entity/location id.
Scenario assumptions affect a temporary clone; they never mutate canon.

## Scenario

```json
{
  "id": "EXT-PHYS-1",
  "title": "Mira touches the live line",
  "actor": "mira",
  "target": "power_line",
  "action": {
    "type": "touch",
    "tags": ["contact", "probe"],
    "description": "Direct contact.",
    "parameters": {}
  },
  "description": "What happens?",
  "focus": "physics",
  "tags": ["external"],
  "real_world_expectation": "Electrical injury.",
  "source": "host-authored",
  "assumptions": [
    {
      "entity_id": "mira",
      "add_tags": ["electrically_insulated"],
      "remove_tags": [],
      "set_properties": {}
    }
  ]
}
```

Assumptions are counterfactual setup scoped to one simulation. They are how the
demo tests "wearing rubber boots" without mutating Mira in canon.

## Markdown ingestion

A documented Markdown source can define entities and locations with headings and
bullets:

```markdown
# My World

## Entities

### mira — Mira Vale
- type: character
- location: street
- tags: human, alive, biological
- properties: health=100, alive=true

## Locations

### street — Bellweather Street
- tags: outdoor, urban
- properties: wet=false

## Canon

- The grid is always live.
```

Any fenced `json` or `yaml` block containing world keys is merged as a
structured fragment:

````markdown
```json
{
  "rules": [
    {
      "id": "r_walk",
      "matcher": {"action_types": ["walk"]},
      "effects": [{"kind": "emit_event", "event": "walked"}]
    }
  ]
}
```
````

Prose that does not follow this shape is preserved in `source_documents` (path,
SHA-256, headings, excerpt) for the host agent; it is not silently converted
into rules.

## Canon lifecycle

```text
proposal (not canon) -> explicit approval -> canon
                             |
                             +-> direct conflict blocks unless overridden
                             +-> regression failure auto-rolls back
rejected / regression_failed -> canon untouched
deprecated -> retained for history, not used by the engine
```
