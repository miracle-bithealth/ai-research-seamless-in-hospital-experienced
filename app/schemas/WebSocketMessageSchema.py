from pydantic import BaseModel
from typing import Optional


class WSRouteMeta(BaseModel):
    type: str = "route_meta"
    total_steps: int
    total_distance_m: float
    estimated_time_s: int
    floors_involved: list[int]
    correlation_id: str = ""


class WSRouteStep(BaseModel):
    type: str = "route_step"
    step: int
    total_steps: int
    floor: int
    instruction: str = ""
    image_url: Optional[str] = None
    svg_data: Optional[str] = None
    distance_m: float = 0.0
    landmarks: list[str] = []


class WSRouteComplete(BaseModel):
    type: str = "route_complete"
    destination: str = ""
    message: str = ""


class WSError(BaseModel):
    type: str = "error"
    code: int = 500
    message: str = ""
