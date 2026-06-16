import inspect

from lichtfeld_mcp.core.gaussian import GaussianId
from lichtfeld_mcp.core.selection_manager import SelectionManager


def test_selection_manager_can_select_gaussian_ids():
    manager = SelectionManager()
    first = GaussianId(1)
    second = GaussianId(2)

    manager.select([first, second])

    assert manager.ids() == [first, second]
    assert manager.count() == 2
    assert manager.selected_count == 2
    assert manager.is_empty() is False
    assert manager.contains(first) is True
    assert manager.contains(GaussianId(999)) is False


def test_selection_manager_deduplicates_and_preserves_order():
    manager = SelectionManager()
    ids = [GaussianId(3), GaussianId(1), GaussianId(3), GaussianId(2), GaussianId(1)]

    manager.select(ids)

    assert manager.ids() == [GaussianId(3), GaussianId(1), GaussianId(2)]
    assert manager.count() == 3


def test_selection_manager_clear_resets_state():
    manager = SelectionManager(selection_mode="add")
    manager.select([GaussianId(1), GaussianId(2)])

    manager.clear()

    assert manager.ids() == []
    assert manager.count() == 0
    assert manager.selected_count == 0
    assert manager.is_empty() is True
    assert manager.selection_mode == "add"


def test_selection_manager_module_has_no_runtime_dependencies():
    source = inspect.getsource(inspect.getmodule(SelectionManager))

    forbidden_tokens = [
        "lichtfeld_mcp.tools",
        "lichtfeld_mcp.services",
        "lichtfeld_mcp.adapters",
        "import mcp",
        "from mcp",
        "SceneService",
        "Lichtfeld",
    ]

    for token in forbidden_tokens:
        assert token not in source
