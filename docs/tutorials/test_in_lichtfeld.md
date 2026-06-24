# Test Lcht_MCP In LichtFeld Studio

## Goal

This tutorial explains two safe ways to validate the current LichtFeld adapter inside LichtFeld Studio:

- an installable plugin package in [examples/lcht_mcp_test_plugin](</c:/Users/icks0/Documents/MCP GS/Lcht_MCP/examples/lcht_mcp_test_plugin>)
- a standalone script in [examples/lichtfeld_plugin_test.py](</c:/Users/icks0/Documents/MCP GS/Lcht_MCP/examples/lichtfeld_plugin_test.py>)

Both options:

- import `LichtfeldAdapter`
- instantiate it
- read scene stats with `get_stats()`
- print the current splat count and bounding box
- run a height selection
- keep the main smoke test non-destructive

## Safety First

`DELETE_SELECTED` is set to `False` by default.

`ENABLE_SAFE_DELETE` is also set to `False` by default.

`CONFIRM_SAFE_DELETE` is also set to `False` by default.

The script never deletes anything unless you explicitly change:

```python
DELETE_SELECTED = True
```

Keep it `False` for initial validation.

The guarded delete validation is a separate flow and remains disabled unless you explicitly change:

```python
ENABLE_SAFE_DELETE = True
CONFIRM_SAFE_DELETE = True
```

Before enabling it, duplicate the source scene and test only on a copy.

## Recommended Option: Install The Plugin On Windows

Copy the folder:

`examples/lcht_mcp_test_plugin`

to:

`C:\Users\icks0\.lichtfeld\plugins\lcht_mcp_test_plugin`

After copying, the installed plugin folder should contain:

- `C:\Users\icks0\.lichtfeld\plugins\lcht_mcp_test_plugin\pyproject.toml`
- `C:\Users\icks0\.lichtfeld\plugins\lcht_mcp_test_plugin\__init__.py`
- `C:\Users\icks0\.lichtfeld\plugins\lcht_mcp_test_plugin\settings.json`
- `C:\Users\icks0\.lichtfeld\plugins\lcht_mcp_test_plugin\core\`
- `C:\Users\icks0\.lichtfeld\plugins\lcht_mcp_test_plugin\operators\`
- `C:\Users\icks0\.lichtfeld\plugins\lcht_mcp_test_plugin\panels\`

The `pyproject.toml` must include a valid `[tool.lichtfeld]` section. Without it, LichtFeld detects the folder but rejects the plugin manifest.

## Configure The Repository Path

The plugin needs access to your `Lcht_MCP` repository so it can import `src/lichtfeld_mcp`.

It looks for the repository in this order:

1. the `LCHT_MCP_REPO_ROOT` environment variable
2. the repository layout when the plugin is run directly from this repo
3. the default Windows hint:
   `C:\Users\<your-user>\Documents\MCP GS\Lcht_MCP`

If your clone is not in that default location, use one of these options:

1. set `LCHT_MCP_REPO_ROOT` before launching LichtFeld Studio
2. edit `REPO_ROOT_HINT` in the installed plugin `core\test_runner.py`

## Restart Or Reload Plugins

After copying the plugin:

1. restart LichtFeld Studio, or
2. use the plugin reload command if your LichtFeld build exposes one

If the plugin system discovers the package successfully, `on_load()` will run automatically.

In the current minimal manifest:

- `[project].name` is the plugin id: `lcht_mcp_test_plugin`
- `[project].description` provides the plugin summary
- `[project].version` declares the plugin version
- `[tool.lichtfeld]` declares LichtFeld compatibility and loader behavior

No separate manifest entry-point field is required in the local plugin manifests we aligned with. LichtFeld loads the plugin package from the folder and uses the package `__init__.py`, which exposes `on_load()` and `on_unload()`.

The plugin now follows the same high-level architecture as the official `360_record` plugin:

- top-level `__init__.py` registers classes with `lf.register_class(...)`
- `panels/` contains the UI panel class
- `operators/` contains the executable operator class
- `core/` contains the safe test runner logic
- `settings.json` enables startup loading

The registration pattern matches the local official plugin:

- `on_load()` registers panel and operator classes
- `on_unload()` unregisters them in reverse order
- the panel button triggers the operator with `lf.ui.ops.invoke(...)`

## Run The Plugin Test

The plugin appears in the same `MAIN_PANEL_TAB` family as `360_record`.

Look for a panel named:

`Lcht MCP Test`

Inside that panel, click:

`Run Lcht MCP Test`

The plugin also exposes a separate guarded destructive validation button:

`Run Safe Delete Test`

For native selection/runtime debugging, the panel also exposes:

- `Diagnose LichtFeld API`
- `Diagnose Tensor Mask Construction`
- `Diagnose Native Selection API`
- `Diagnose Apply Deleted Selection Lifetime`

For cleanup category visibility, the panel also exposes:

- `Show Floating Clusters`
- `Show Disconnected Clusters`
- `Show Distant Outliers`
- `Show Sparse Regions`
- `Preview Selected Category`
- `Preview All Cleanup Categories`

The panel button invokes the registered operator through:

`lfs_plugins.lcht_mcp_test_plugin.operators.run_test.LCHTMCP_OT_run_test`

If you want to trigger the operator manually from the LichtFeld Python console, run:

```python
import lichtfeld as lf
lf.ui.ops.invoke("lfs_plugins.lcht_mcp_test_plugin.operators.run_test.LCHTMCP_OT_run_test")
```

If you prefer to run the underlying function directly from Python:

```python
from lcht_mcp_test_plugin.core.test_runner import run_lcht_mcp_test
run_lcht_mcp_test()
```

For the guarded delete flow:

```python
from lcht_mcp_test_plugin.core.test_runner import run_safe_delete_test
run_safe_delete_test()
```

For the permanent-apply selection lifetime trace:

```python
from lcht_mcp_test_plugin.core.diagnostics import run_apply_deleted_selection_lifetime_diagnostics
run_apply_deleted_selection_lifetime_diagnostics()
```

## Change The Height Range

Edit the installed plugin:

`C:\Users\icks0\.lichtfeld\plugins\lcht_mcp_test_plugin\core\test_runner.py`

and update:

```python
MIN_Z = 0.0
MAX_Z = 2.0
```

The adapter already normalizes inverted ranges, but keeping `MIN_Z <= MAX_Z` is easier to read while testing.

## Why Delete Is Disabled By Default

The plugin ships with:

```python
DELETE_SELECTED = False
ENABLE_SAFE_DELETE = False
CONFIRM_SAFE_DELETE = False
```

This prevents destructive operations during a first validation pass.

Only enable the guarded delete flow after you confirm the height selection is targeting the expected splats on a copied dataset.

## Safe Delete Test

`Run Lcht MCP Test` remains non-destructive.

`Run Safe Delete Test` is a separate guarded workflow.

It requires a two-stage safety gate:

- `ENABLE_SAFE_DELETE=True`
- `CONFIRM_SAFE_DELETE=True`

When `ENABLE_SAFE_DELETE=False`:

- the plugin logs that the delete test is disabled
- no selection is deleted
- the operator returns successfully

When `ENABLE_SAFE_DELETE=True` but `CONFIRM_SAFE_DELETE=False`:

- the plugin logs that deletion is armed but not confirmed
- no selection is deleted
- the operator returns successfully

Only when both flags are `True`, the plugin:

1. reads initial stats
2. selects a narrow default range:
   `min_z = 1.0`, `max_z = 1.02`
3. logs:
   - `selected_count`
   - percentage of total splats
4. refuses to delete when any guard triggers:
   - `selected_count == 0`
   - `selected_count > 50_000`
   - `selected_count / total > 0.05`
5. deletes only if all guards pass
6. logs final splat count and computed deleted count
7. clears selection before exit when possible

Always duplicate the scene and validate on a copy first.

Recommended progression:

1. Run with `ENABLE_SAFE_DELETE=False` and `CONFIRM_SAFE_DELETE=False`
2. Then run with `ENABLE_SAFE_DELETE=True` and `CONFIRM_SAFE_DELETE=False`
3. Only on a duplicated PLY, run with both `ENABLE_SAFE_DELETE=True` and `CONFIRM_SAFE_DELETE=True`

## Cleanup Category Preview

`Cleanup Workspace` and `Compare Cleanup Presets` stay non-destructive.

`Preview Selected Category` and `Preview All Cleanup Categories` also stay
non-destructive. They reuse the current cleanup workspace sample and only update
native selection.

The current category model is:

- `FLOATING_VOXEL_CLUSTERS`
- `DISCONNECTED_CLUSTERS`
- `DISTANT_OUTLIERS`
- `SPARSE_SINGLETON_REGIONS`

Recommended workflow:

1. Run `Analyze Scene`
2. Open `Cleanup Workspace`
3. Optionally run `Compare Cleanup Presets`
4. Toggle one or more cleanup categories
5. Run `Preview Selected Category` or `Preview All Cleanup Categories`

Current limitation:

- the preview is category-isolated native selection only
- the plugin does not yet render per-category colors in the viewport

Future path:

- keep the same workspace category data
- swap the native selection-only visualization for a color-coded overlay once
  the LichtFeld runtime exposes a stable multi-color API

## Diagnose Apply Deleted Selection Lifetime

Use `Diagnose Apply Deleted Selection Lifetime` when Cleanup Workspace soft delete and
permanent apply succeed at the plugin level, but the native runtime later reports
selection-tensor lifetime errors such as stale mask sizes or invalid tensor clones.

This diagnostic:

1. requires `ENABLE_SAFE_DELETE=True` and `CONFIRM_SAFE_DELETE=True`
2. requires an already pending reversible Cleanup Workspace soft delete
3. logs object ids, refcounts, tensor sizes, and clone results for selection-related
   owners visible from the LichtFeld Python API
4. traces the state:
   - before `apply_cleanup_workspace_deleted()`
   - immediately after `apply_cleanup_workspace_deleted()`
   - after reacquiring fresh scene/model handles
5. reports the first stale-size owner and the first owner whose `clone()` fails

This repository does not vendor the native LichtFeld runtime source itself, so this
diagnostic is the intended way to identify the exact Python-visible owner before
patching the native runtime.

## What The Plugin Does

The non-destructive smoke test runs each step in its own `try/except` block and logs a clear message:

1. Configure `sys.path` for the local `src/` directory.
2. Import and instantiate `LichtfeldAdapter`.
3. Call `get_stats()`.
4. Print:
   - `splat_count`
   - `bounding_box` from `stats.bounds`
5. Call `select_by_height(z_min=MIN_Z, z_max=MAX_Z)`.
6. Print `selected_count`.
7. Clear the selection before exit.

The guarded delete flow also wraps each step in its own `try/except` block and only deletes after the hard safety thresholds pass.

The plugin uses the same logging style as the official local plugin family:

- `lf.log.info(...)` for normal lifecycle and execution messages
- `lf.log.error(...)` for failures

## Expected Output

Typical success output looks like:

```text
lcht_mcp_test_plugin loaded
lcht_mcp_test_plugin: Starting safe adapter smoke test with MIN_Z=0.0, MAX_Z=2.0, DELETE_SELECTED=False.
lcht_mcp_test_plugin: LichtfeldAdapter instantiated from C:\Users\icks0\Documents\MCP GS\Lcht_MCP.
lcht_mcp_test_plugin: splat_count=123456
lcht_mcp_test_plugin: bounding_box=min=Vec3(x=-2.1, y=-1.0, z=0.0) max=Vec3(x=4.8, y=3.2, z=7.4)
lcht_mcp_test_plugin: ----------------------------------------
lcht_mcp_test_plugin: Selection range: min_z=0.0 max_z=2.0
lcht_mcp_test_plugin: selected_count=8421
lcht_mcp_test_plugin: percentage_of_total=6.820000%
lcht_mcp_test_plugin: ----------------------------------------
lcht_mcp_test_plugin: Selection cleared before exit.
lcht_mcp_test_plugin: Validation complete. DELETE_SELECTED=False; selection cleared.
```

Using the actual official plugin architecture, there is no separate dynamic button-registration log. The button becomes available because the panel class is registered during `on_load()`.

If there is a problem, the plugin prints a clear error for the failing step, for example:

```text
lcht_mcp_test_plugin: get_stats failed: No active LichtFeld scene is available.
```

## Standalone Script Fallback

If you do not want to install the plugin package yet, you can still use the standalone script:

```python
import lichtfeld_plugin_test
lichtfeld_plugin_test.main()
```

This keeps the same safe default behavior with `DELETE_SELECTED = False`.

## Troubleshooting

If the plugin does not appear in LichtFeld Studio:

1. confirm the folder name is exactly `lcht_mcp_test_plugin`
2. confirm the folder contains `pyproject.toml`, `__init__.py`, `settings.json`, `core\`, `operators\`, and `panels\`
3. confirm `pyproject.toml` contains a `[tool.lichtfeld]` section
4. restart LichtFeld Studio or reload plugins again
5. check the LichtFeld logs for `lcht_mcp_test_plugin loaded`
6. confirm the `Lcht_MCP` repository is reachable through `LCHT_MCP_REPO_ROOT` or `REPO_ROOT_HINT`
7. confirm that `src\lichtfeld_mcp` exists in that repository

If the plugin loads but the panel does not appear:

1. check that the panel space is the main side panel tab, the same family used by `360_record`
2. confirm that `on_load()` completed without a class registration error
3. run the operator manually with:
   `lf.ui.ops.invoke("lfs_plugins.lcht_mcp_test_plugin.operators.run_test.LCHTMCP_OT_run_test")`
4. if needed, run `from lcht_mcp_test_plugin.core.test_runner import run_lcht_mcp_test`
5. then call `run_lcht_mcp_test()` directly to isolate UI registration from adapter execution
