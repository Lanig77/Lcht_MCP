from dataclasses import dataclass


@dataclass(slots=True)
class EditManager:
    history_depth: int = 0
    undo_available: bool = False
