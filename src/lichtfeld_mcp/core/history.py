from __future__ import annotations

from dataclasses import dataclass, field

from .gaussian import Gaussian, GaussianId


@dataclass(frozen=True, slots=True)
class GaussianRestorePoint:
    index: int
    gaussian: Gaussian


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    action: str
    affected_ids: tuple[GaussianId, ...] = ()
    details: dict[str, object] = field(default_factory=dict)
    restore_points: tuple[GaussianRestorePoint, ...] = ()


@dataclass(slots=True)
class HistoryStack:
    _entries: list[HistoryEntry] = field(default_factory=list, repr=False)

    def push(self, entry: HistoryEntry) -> None:
        self._entries.append(entry)

    def peek(self) -> HistoryEntry | None:
        if not self._entries:
            return None
        return self._entries[-1]

    def pop(self) -> HistoryEntry | None:
        if not self._entries:
            return None
        return self._entries.pop()

    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def count(self) -> int:
        return len(self._entries)

    def is_empty(self) -> bool:
        return not self._entries
