from __future__ import annotations

from dataclasses import dataclass, field

from .gaussian_cloud import GaussianCloud
from .history import HistoryEntry, HistoryStack
from .selection_manager import SelectionManager

@dataclass(slots=True)
class EditManager:
    history_depth: int = 0
    undo_available: bool = False
    _gaussians: GaussianCloud | None = field(default=None, repr=False)
    _selection: SelectionManager | None = field(default=None, repr=False)
    _history: HistoryStack | None = field(default=None, repr=False)

    def attach(
        self,
        gaussians: GaussianCloud,
        selection: SelectionManager,
        history: HistoryStack | None = None,
    ) -> None:
        self._gaussians = gaussians
        self._selection = selection
        self._history = history

    def delete_selected(self) -> int:
        if self._gaussians is None or self._selection is None or self._selection.is_empty():
            return 0
        selected_ids = self._selection.ids()
        affected_ids = tuple(
            gaussian_id
            for gaussian_id in selected_ids
            if self._gaussians.get(gaussian_id) is not None
        )
        deleted = self._gaussians.remove_many(selected_ids)
        if deleted > 0 and self._history is not None:
            self._history.push(
                HistoryEntry(
                    action="delete_selected",
                    affected_ids=affected_ids,
                    details={"deleted_count": deleted},
                )
            )
        self._selection.clear()
        return deleted
