# Markdown Test World

A compact world used to verify deterministic Markdown ingestion.

## Entities

### tala — Tala the Mason
- type: character
- location: yard
- tags: human, biological, actor
- properties: health=50, alive=true
- description: A mason with a bad shoulder.

### stone — Practice Stone
- type: object
- location: yard
- tags: heavy, stone
- properties: integrity=10, weight=40
- description: A stone used for lifting practice.

## Locations

### yard — Work Yard
- tags: outdoor, test
- properties: wet=false
- description: A small yard behind the workshop.

## Rules

```json
{
  "rules": [
    {
      "id": "r_lift_stone",
      "name": "Lifting a stone",
      "description": "A human who lifts a stone makes it move but risks strain.",
      "domain": "physics",
      "matcher": {
        "action_types": ["lift"],
        "actor_tags_any": ["human"],
        "target_tags_any": ["stone"]
      },
      "effects": [
        {"kind": "add_tag", "target": "target", "tag": "lifted"},
        {"kind": "modify_property", "target": "actor", "property": "health", "delta": -2},
        {"kind": "emit_event", "target": "actor", "event": "strain", "message": "the lift strains the actor"}
      ],
      "priority": 50,
      "status": "canon",
      "version": 1
    }
  ]
}
```

## Canon

- Tala works in the yard.
- The practice stone is heavy but liftable.
