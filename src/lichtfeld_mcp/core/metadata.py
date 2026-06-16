from dataclasses import dataclass


@dataclass(slots=True)
class Metadata:
    project_name: str | None = None
    project_path: str | None = None
    project_id: str | None = None
