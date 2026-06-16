from dataclasses import dataclass


@dataclass(slots=True)
class SelectionManager:
    selected_count: int = 0
    selection_mode: str = "replace"
