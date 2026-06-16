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

## Configure The Repository Path

The plugin needs access to your `Lcht_MCP` repository so it can import `src/lichtfeld_mcp`.

It looks for the repository in this order:

1. the `LCHT_MCP_REPO_ROOT` environment variable
2. the repository layout when the plugin is run directly from this repo
3. the default Windows hint:
   `C:\Users\<your-user>\Documents\MCP GS\Lcht_MCP`

If your clone is not in that default location, use one of these options:

1. set `LCHT_MCP_REPO_ROOT` before launching LichtFeld Studio
2. edit `REPO_ROOT_HINT` in the installed plugin `__init__.py`

## Restart Or Reload Plugins

After copying the plugin:

1. restart LichtFeld Studio, or
2. use the plugin reload command if your LichtFeld build exposes one

If the plugin system discovers the package successfully, `on_load()` will run automatically.

## Run The Plugin Test

If LichtFeld exposes a compatible UI registration API, the plugin will register a button or action named:

`Run Lcht MCP Test`

Click that button or action to run the smoke test.

If no compatible UI registration API is available, the plugin logs a clear fallback message. In that case, run it manually from the LichtFeld Python console:

```python
import lcht_mcp_test_plugin
lcht_mcp_test_plugin.run_lcht_mcp_test()
```

## Change The Height Range

Edit the installed plugin `__init__.py` and update:

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

The plugin prefers `lf.log.info(...)` and `lf.log.error(...)` when available, and falls back to `print(...)` otherwise.

## Expected Output

Typical success output looks like:

```text
[Lcht_MCP Plugin] lcht_mcp_test_plugin loaded.
[Lcht_MCP Plugin] Registered 'Run Lcht MCP Test' via LichtFeld UI API (register_button).
[Lcht_MCP Plugin] Starting safe adapter smoke test with MIN_Z=0.0, MAX_Z=2.0, DELETE_SELECTED=False.
[Lcht_MCP Plugin] LichtfeldAdapter instantiated from C:\Users\icks0\Documents\MCP GS\Lcht_MCP.
[Lcht_MCP Plugin] splat_count=123456
[Lcht_MCP Plugin] bounding_box=min=Vec3(x=-2.1, y=-1.0, z=0.0) max=Vec3(x=4.8, y=3.2, z=7.4)
[Lcht_MCP Plugin] select_by_height range: min_z=0.0, max_z=2.0
[Lcht_MCP Plugin] selected_count=8421
[Lcht_MCP Plugin] delete_selection skipped because DELETE_SELECTED=False.
```

If UI registration is not available, a normal fallback message looks like:

```text
[Lcht_MCP Plugin] UI registration is not available. Run lcht_mcp_test_plugin.run_lcht_mcp_test() manually from the LichtFeld Python console.
```

If there is a problem, the plugin prints a clear error for the failing step, for example:

```text
[Lcht_MCP Plugin] get_stats failed: No active LichtFeld scene is available.
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
2. confirm the folder contains both `pyproject.toml` and `__init__.py`
3. restart LichtFeld Studio or reload plugins again
4. check the LichtFeld logs for `lcht_mcp_test_plugin loaded`
5. confirm the `Lcht_MCP` repository is reachable through `LCHT_MCP_REPO_ROOT` or `REPO_ROOT_HINT`
6. confirm that `src\lichtfeld_mcp` exists in that repository

If the plugin loads but the button does not appear:

1. look for the manual fallback log message
2. run `lcht_mcp_test_plugin.run_lcht_mcp_test()` from the Python console
3. keep using the plugin this way until the exact LichtFeld UI API is known for your build
