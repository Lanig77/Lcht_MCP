from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MIN_Z = 0.0
MAX_Z = 2.0
DELETE_SELECTED = False


def configure_import_path() -> None:
    src_path = REPO_ROOT / "src"
    if not src_path.exists():
        raise RuntimeError(
            f"Could not find '{src_path}'. "
            "If you copied this file outside the repository, update REPO_ROOT first."
        )
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def build_adapter():
    configure_import_path()
    from lichtfeld_mcp.adapters.lichtfeld import LichtfeldAdapter

    return LichtfeldAdapter()


def main() -> None:
    try:
        adapter = build_adapter()
        print("[Lcht_MCP] LichtfeldAdapter instantiated.")
    except Exception as exc:
        print(f"[Lcht_MCP] Adapter setup failed: {exc}")
        return

    try:
        stats = adapter.get_stats()
        bounding_box = stats.bounds
        print(f"[Lcht_MCP] splat_count={stats.splat_count}")
        print(f"[Lcht_MCP] bounding_box={bounding_box}")
    except Exception as exc:
        print(f"[Lcht_MCP] get_stats failed: {exc}")

    try:
        print(f"[Lcht_MCP] select_by_height range: min_z={MIN_Z}, max_z={MAX_Z}")
        selection = adapter.select_by_height(z_min=MIN_Z, z_max=MAX_Z)
        print(f"[Lcht_MCP] selected_count={selection.selected_count}")
    except Exception as exc:
        print(f"[Lcht_MCP] select_by_height failed: {exc}")

    if not DELETE_SELECTED:
        print("[Lcht_MCP] delete_selection skipped because DELETE_SELECTED=False.")
        return

    try:
        delete_result = adapter.delete_selection()
        print(f"[Lcht_MCP] delete_selection: ok={delete_result.ok} message={delete_result.message}")
    except Exception as exc:
        print(f"[Lcht_MCP] delete_selection failed: {exc}")


if __name__ == "__main__":
    main()
