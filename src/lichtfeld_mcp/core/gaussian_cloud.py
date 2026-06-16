from dataclasses import dataclass


@dataclass(slots=True)
class GaussianCloud:
    splat_count: int = 0
    sh_degree: int = 0
    format_name: str | None = None
