from dataclasses import dataclass


@dataclass(slots=True)
class Capabilities:
    supports_selection: bool = False
    supports_editing: bool = False
    supports_measurement: bool = False
    supports_export: bool = False
