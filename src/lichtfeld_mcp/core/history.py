from __future__ import annotations

from dataclasses import dataclass, field

from .gaussian import GaussianId


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    action: str
    affected_ids: tuple[GaussianId, ...] = ()
    details: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class HistoryStack:
    _entries: list[HistoryEntry] = field(default_factory=list, repr=False)

    def push(self, entry: HistoryEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def count(self) -> int:
        return len(self._entries)

    def is_empty(self) -> bool:
        return not self._entries
