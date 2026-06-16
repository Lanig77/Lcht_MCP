"""Small CLI for testing the adapter without an MCP client."""

from __future__ import annotations

import argparse
import json

from lichtfeld_mcp.app_state import get_scene_api


def main() -> None:
    parser = argparse.ArgumentParser(description="Local dev CLI for the Lichtfeld MCP scene API")
    parser.add_argument("project", nargs="?", default="demo_scene.lfp")
    args = parser.parse_args()

    scene_api = get_scene_api()
    outputs = []
    outputs.append(scene_api.open_project(args.project).model_dump())
    outputs.append(scene_api.get_scene_stats().model_dump())
    outputs.append(scene_api.select_by_box(-1, -1, 0, 1, 1, 2).model_dump())
    outputs.append(scene_api.delete_selection().model_dump())
    outputs.append(scene_api.optimize_for_target("quest3").model_dump())
    outputs.append(scene_api.export_scene("out/scene.spz", "spz", target="quest3").model_dump())
    print(json.dumps(outputs, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
