# Test Lcht_MCP In LichtFeld Studio

## Goal

This tutorial explains two safe ways to smoke-test the current LichtFeld adapter inside LichtFeld Studio:

- an installable plugin package in [examples/lcht_mcp_test_plugin](</c:/Users/icks0/Documents/MCP GS/Lcht_MCP/examples/lcht_mcp_test_plugin>)
- a standalone script in [examples/lichtfeld_plugin_test.py](</c:/Users/icks0/Documents/MCP GS/Lcht_MCP/examples/lichtfeld_plugin_test.py>)

Both options:

- import `LichtfeldAdapter`
- instantiate it
- read scene stats with `get_stats()`
- print the current splat count and bounding box
- run a height selection
- optionally delete the current selection

## Safety First

`DELETE_SELECTED` is set to `False` by default.

The script never deletes anything unless you explicitly change:

```python
DELETE_SELECTED = True
```

Keep it `False` for initial validation.

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
```

This prevents destructive operations during a first validation pass.

Only change it to `True` after you confirm the height selection is targeting the expected splats.

## What The Plugin Does

The plugin runs each step in its own `try/except` block and logs a clear message:

1. Configure `sys.path` for the local `src/` directory.
2. Import and instantiate `LichtfeldAdapter`.
3. Call `get_stats()`.
4. Print:
   - `splat_count`
   - `bounding_box` from `stats.bounds`
5. Call `select_by_height(z_min=MIN_Z, z_max=MAX_Z)`.
6. Print `selected_count`.
7. Call `delete_selection()` only if `DELETE_SELECTED` was changed to `True`.

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
lcht_mcp_test_plugin: select_by_height range: min_z=0.0, max_z=2.0
lcht_mcp_test_plugin: selected_count=8421
lcht_mcp_test_plugin: delete_selection skipped because DELETE_SELECTED=False.
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
