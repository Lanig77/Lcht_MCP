from __future__ import annotations

from dataclasses import dataclass, field

from .gaussian_cloud import GaussianCloud
from .gaussian import GaussianId
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
        self._sync_history_state()

    def delete_selected(self) -> int:
        if self._gaussians is None or self._selection is None or self._selection.is_empty():
            return 0
        selected_ids = self._selection.ids()
        before_state = self._gaussians.snapshot(selected_ids)
        affected_ids = tuple(restore_point.gaussian.id for restore_point in before_state)
        deleted = self._gaussians.remove_many(selected_ids)
        if deleted > 0 and self._history is not None:
            self._history.push(
                HistoryEntry(
                    action_type="delete_selected",
                    affected_ids=affected_ids,
                    before_state=before_state,
                    metadata={"deleted_count": deleted},
                )
            )
        self._selection.clear()
        self._sync_history_state()
        return deleted

    def undo_last(self) -> bool:
        if self._gaussians is None or self._selection is None or self._history is None:
            return False
        entry = self._history.peek()
        if entry is None or not entry.before_state:
            self._sync_history_state()
            return False
        before_ids = {restore_point.gaussian.id.value for restore_point in entry.before_state}
        after_ids = {restore_point.gaussian.id.value for restore_point in entry.after_state}
        created_ids = tuple(
            GaussianId(value=gaussian_id)
            for gaussian_id in sorted(after_ids - before_ids)
        )
        if created_ids:
            self._gaussians.remove_many(created_ids)
        self._gaussians.replace_many(
            restore_point.gaussian
            for restore_point in entry.before_state
            if self._gaussians.get(restore_point.gaussian.id) is not None
        )
        self._gaussians.restore_many(
            (restore_point.index, restore_point.gaussian)
            for restore_point in entry.before_state
            if self._gaussians.get(restore_point.gaussian.id) is None
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
