from dataclasses import dataclass


@dataclass(slots=True)
class Statistics:
    splat_count: int = 0
    selected_count: int = 0
    estimated_vram_mb: float = 0.0
