from __future__ import annotations

from dataclasses import dataclass, field

from .gaussian_cloud import GaussianCloud
from .selection_manager import SelectionManager

@dataclass(slots=True)
class EditManager:
    history_depth: int = 0
    undo_available: bool = False
    _gaussians: GaussianCloud | None = field(default=None, repr=False)
    _selection: SelectionManager | None = field(default=None, repr=False)

    def attach(self, gaussians: GaussianCloud, selection: SelectionManager) -> None:
        self._gaussians = gaussians
        self._selection = selection

    def delete_selected(self) -> int:
        if self._gaussians is None or self._selection is None or self._selection.is_empty():
            return 0
        deleted = self._gaussians.remove_many(self._selection.ids())
        self._selection.clear()
        return deleted
