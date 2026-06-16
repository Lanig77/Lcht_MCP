from dataclasses import dataclass


@dataclass(slots=True)
class ExportManager:
    last_output_path: str | None = None
    last_format: str | None = None
