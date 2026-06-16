from dataclasses import dataclass


@dataclass(slots=True)
class CameraSet:
    camera_count: int = 0
    active_camera_id: str | None = None
