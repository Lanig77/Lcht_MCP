from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .gaussian import GaussianId


@dataclass(slots=True)
class SelectionManager:
    selected_count: int = 0
    selection_mode: str = "replace"
    _selected_ids: list[GaussianId] = field(default_factory=list, repr=False)
    _selected_index: set[int] = field(default_factory=set, repr=False)

    def select(self, ids: Iterable[GaussianId]) -> None:
        for gaussian_id in ids:
            if gaussian_id.value in self._selected_index:
                continue
            self._selected_ids.append(gaussian_id)
            self._selected_index.add(gaussian_id.value)
        self.selected_count = len(self._selected_ids)

    def clear(self) -> None:
        self._selected_ids.clear()
        self._selected_index.clear()
        self.selected_count = 0

    def ids(self) -> list[GaussianId]:
        return list(self._selected_ids)

    def count(self) -> int:
        return len(self._selected_ids)

    def is_empty(self) -> bool:
        return not self._selected_ids

    def contains(self, id: GaussianId) -> bool:
        return id.value in self._selected_index
