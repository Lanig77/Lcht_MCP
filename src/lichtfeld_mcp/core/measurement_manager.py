from dataclasses import dataclass


@dataclass(slots=True)
class MeasurementManager:
    last_distance: float | None = None
    unit: str = "m"
