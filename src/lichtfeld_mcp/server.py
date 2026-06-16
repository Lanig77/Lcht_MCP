"""MCP server entrypoint.

Run locally:
    python -m lichtfeld_mcp.server

Or, after installation:
    lichtfeld-mcp
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lichtfeld_mcp.tools import edit, export, measure, optimize, scene, selection

mcp = FastMCP("Lichtfeld Gaussian Editor")

# Scene tools
mcp.tool()(scene.open_project)
mcp.tool()(scene.save_project)
mcp.tool()(scene.close_project)
mcp.tool()(scene.get_scene_stats)
mcp.tool()(scene.list_history)
mcp.tool()(scene.undo)

# Selection/edit tools
mcp.tool()(selection.select_by_box)
mcp.tool()(selection.select_by_height)
mcp.tool()(selection.select_by_color)
mcp.tool()(selection.delete_selection)
mcp.tool()(edit.crop_by_box)
mcp.tool()(edit.crop_by_height)

# Optimize/export/measure tools
mcp.tool()(optimize.optimize_for_target)
mcp.tool()(export.export_scene)
mcp.tool()(measure.measure_distance)


def main() -> None:
    """Start the MCP server over stdio."""

    mcp.run()


if __name__ == "__main__":
    main()
