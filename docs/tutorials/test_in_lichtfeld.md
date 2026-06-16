# Test Lcht_MCP In LichtFeld Studio

## Goal

This tutorial provides a minimal manual test harness for the current LichtFeld plugin adapter.

Use [examples/lichtfeld_plugin_test.py](</c:/Users/icks0/Documents/MCP GS/Lcht_MCP/examples/lichtfeld_plugin_test.py>) to:

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

## Prepare The Script

1. Open a Gaussian scene in LichtFeld Studio.
2. Copy `examples/lichtfeld_plugin_test.py` into your LichtFeld plugin or script area, or run it directly from this repository.
3. If you copied the file outside the repository, update the `REPO_ROOT` constant so it points to your local `Lcht_MCP` checkout.
4. Confirm that `DELETE_SELECTED = False`.
5. Adjust the selection range if needed:

```python
MIN_Z = 0.0
MAX_Z = 2.0
```

## Run Inside LichtFeld Studio

Run the script from the LichtFeld Studio Python/script runner.

If your setup executes files directly, the script will call `main()` automatically.

If you prefer to import it first, then run:

```python
import lichtfeld_plugin_test
lichtfeld_plugin_test.main()
```

## What The Script Does

The harness runs each step in its own `try/except` block and prints a clear message:

1. Configure `sys.path` for the local `src/` directory.
2. Import and instantiate `LichtfeldAdapter`.
3. Call `get_stats()`.
4. Print:
   - `splat_count`
   - `bounding_box` from `stats.bounds`
5. Call `select_by_height(z_min=MIN_Z, z_max=MAX_Z)`.
6. Print `selected_count`.
7. Call `delete_selection()` only if `DELETE_SELECTED` was changed to `True`.

## Expected Console Output

Typical success output looks like:

```text
[Lcht_MCP] LichtfeldAdapter instantiated.
[Lcht_MCP] splat_count=123456
[Lcht_MCP] bounding_box=min=Vec3(x=-2.1, y=-1.0, z=0.0) max=Vec3(x=4.8, y=3.2, z=7.4)
[Lcht_MCP] select_by_height range: min_z=0.0, max_z=2.0
[Lcht_MCP] selected_count=8421
[Lcht_MCP] delete_selection skipped because DELETE_SELECTED=False.
```

If there is a problem, the script prints a clear error for the failing step, for example:

```text
[Lcht_MCP] get_stats failed: No active LichtFeld scene is available.
```

## Changing The Height Range

Only edit these constants:

```python
MIN_Z = 1.5
MAX_Z = 3.0
```

The adapter already normalizes inverted ranges, but using a clear lower-to-upper range is easier to read while testing.

## Deletion Is Optional

To test deletion manually, change:

```python
DELETE_SELECTED = True
```

Do this only after confirming that the height selection is targeting the expected splats.

For normal smoke tests, leave deletion disabled.
