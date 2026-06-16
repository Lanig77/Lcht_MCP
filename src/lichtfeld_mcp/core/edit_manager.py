from __future__ import annotations

from dataclasses import dataclass, field

from .gaussian_cloud import GaussianCloud
from .history import GaussianRestorePoint, HistoryEntry, HistoryStack
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
        self._sync_history_state()

    def delete_selected(self) -> int:
        if self._gaussians is None or self._selection is None or self._selection.is_empty():
            return 0
        selected_ids = self._selection.ids()
        selected_values = {gaussian_id.value for gaussian_id in selected_ids}
        restore_points = tuple(
            GaussianRestorePoint(index=index, gaussian=gaussian)
            for index, gaussian in enumerate(self._gaussians.gaussians)
            if gaussian.id.value in selected_values
        )
        affected_ids = tuple(restore_point.gaussian.id for restore_point in restore_points)
        deleted = self._gaussians.remove_many(selected_ids)
        if deleted > 0 and self._history is not None:
            self._history.push(
                HistoryEntry(
                    action="delete_selected",
                    affected_ids=affected_ids,
                    details={"deleted_count": deleted},
                    restore_points=restore_points,
                )
            )
        self._selection.clear()
        self._sync_history_state()
        return deleted

    def undo_last(self) -> bool:
        if self._gaussians is None or self._selection is None or self._history is None:
            return False
        entry = self._history.peek()
        if entry is None or entry.action != "delete_selected" or not entry.restore_points:
            self._sync_history_state()
            return False
        self._gaussians.restore_many(
            (restore_point.index, restore_point.gaussian)
            for restore_point in entry.restore_points
        )
        self._history.pop()
        self._selection.clear()
        self._sync_history_state()
        return True

    def _sync_history_state(self) -> None:
        if self._history is None:
            self.history_depth = 0
            self.undo_available = False
            return
        self.history_depth = self._history.count()
        self.undo_available = not self._history.is_empty()
