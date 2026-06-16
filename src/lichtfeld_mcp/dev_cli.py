"""Small CLI for testing the adapter without an MCP client."""

from __future__ import annotations

import argparse
import json

from lichtfeld_mcp.app_state import get_adapter
from lichtfeld_mcp.schemas.common import Box3D, Vec3


def main() -> None:
    parser = argparse.ArgumentParser(description="Local dev CLI for the Lichtfeld MCP adapter")
    parser.add_argument("project", nargs="?", default="demo_scene.lfp")
    args = parser.parse_args()

    adapter = get_adapter()
    outputs = []
    outputs.append(adapter.open_project(args.project).model_dump())
    outputs.append(adapter.get_scene_stats().model_dump())
    outputs.append(
        adapter.select_by_box(
            Box3D(min=Vec3(x=-1, y=-1, z=0), max=Vec3(x=1, y=1, z=2))
        ).model_dump()
    )
    outputs.append(adapter.delete_selection().model_dump())
    outputs.append(adapter.optimize_for_target("quest3").model_dump())
    outputs.append(adapter.export_scene("out/scene.spz", "spz", target="quest3").model_dump())
    print(json.dumps(outputs, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
