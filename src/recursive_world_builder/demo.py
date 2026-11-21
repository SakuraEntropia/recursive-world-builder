"""End-to-end demo on examples/electric_city."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .storage import load_world, save_world
from .controller import Controller, RunConfig
from .explorer import Scenario


def predefined_probes() -> list[Scenario]:
    return [
        Scenario(id="p1", verb="touch", subjects=["person_1"], objects=["line_1"], intent="person touches live line"),
        Scenario(id="p2", verb="enter", subjects=["pool_1"], objects=["person_1"], intent="person enters pool"),
        Scenario(id="p3", verb="strike", subjects=["car_1"], objects=["line_1"], intent="car hits pole"),
        Scenario(id="p4", verb="touch", subjects=["person_1"], objects=["boots_1"], intent="insulated contact"),
    ]


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("examples/electric_city")
    world = load_world(root)
    errors = world.validate()
    if errors:
        print("world errors:", errors)
        return 1

    ctl = Controller(world, RunConfig(rounds=3, max_scenarios=20, max_proposals=5))
    report = ctl.run(probes=predefined_probes())

    print(f"rounds={report.rounds_run} scenarios={report.scenarios} "
          f"findings={len(report.findings)} proposals={len(report.proposals)} "
          f"stopped={report.stopped_because}")

    if report.proposals:
        pid = report.proposals[0]["id"]
        print("approving", pid)
        ctl.approve(pid)
        print("rules now:", sorted(world.rules))
        follow = ctl.follow_ups(pid)
        print("counterfactual scenarios:", len(follow))
        again = ctl.run(probes=follow)
        print("second pass findings:", len(again.findings))

    out = root / "world.after.json"
    out.write_text(json.dumps(world.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
