# Electric City

Electric City is a near-contemporary river city whose power grid is live at all
hours. The setting was originally written as a mood piece, so the prose
establishes atmosphere and social texture but says almost nothing about
electrical physics. That silence is the point of the demo.

## Canon

- The high-voltage line above Bellweather Street is always energized.
- The city treats the grid as public infrastructure and publishes no safety code.
- Mira Vale has lived on Bellweather Street for six years and has never seen electricity injure anyone.
- The pool in the courtyard is fed by the river and is deep enough to submerge an adult.
- The city council has never defined a procedure for ordinary residents who petition it.

## Entities

### mira — Mira Vale
- type: character
- location: street
- tags: human, alive, biological, actor, citizen
- properties: health=100, alive=true, wealth=5
- description: A courier who knows every shortcut in the district.

### power_line — Bellweather High-Voltage Line
- type: object
- location: street
- tags: electrical, energized, conductor, outdoor, hazard
- properties: voltage=10000, current=200, operational=true, integrity=100
- description: A live feeder line strung above the street on a weathered pole.

### pole — Bellweather Utility Pole
- type: object
- location: street
- tags: infrastructure, structural, pole, tall, outdoor
- properties: integrity=100
- description: The pole supports the live feeder line.

### pool_water — Courtyard Pool
- type: object
- location: pool
- tags: water, liquid, fluid, conductive, outdoor
- properties: volume=5000, depth=2.0, energized=false
- description: Cold river water in a tiled public pool.

### car — Delivery Car
- type: vehicle
- location: street
- tags: vehicle, car, metal, conductor, movable
- properties: speed=0, integrity=100
- description: A compact electric delivery car with a dented bumper.

### crate — Cargo Crate
- type: object
- location: street
- tags: fragile, crate, wood
- properties: integrity=50
- description: A stack of produce crates waiting for pickup.

### insulated_boots — Rubber Boots
- type: object
- location: street
- tags: rubber, insulator, wearable, electrically_insulated
- properties: insulation=1000
- description: Heavy rubber work boots left by a utility crew.

### council — City Council Office
- type: institution
- location: street
- tags: institution, government, law, society
- properties: legitimacy=0.8
- description: A public office with an unstaffed petition desk.

### substation — Fenced Substation
- type: object
- location: street
- tags: infrastructure, substation, electrical, energized, outdoor
- properties: integrity=100
- description: A fenced transformer yard marked with faded warnings.

## Constraints

- Residents are prohibited from entering or sabotaging the fenced substation.
- Weather in Electric City is atmospheric only; the prose has not defined storm damage.
- Electrical effects must remain consistent with the city's always-live grid.

## Notes for the host agent

The city is not a physics textbook. If an exploration result suggests that
gravity, time, or biology differ from the real world, treat that as a possible
fictional axiom rather than an error. The demo's local gap is the missing
electrical mechanism, not the absence of every possible rule.
