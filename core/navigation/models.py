from typing import Optional

from pydantic import BaseModel, Field


class NodeData(BaseModel):
    id: str
    name: str = ""
    floor: int = 1
    x: float = 0.0
    y: float = 0.0
    type: str = "junction"
    accessible: bool = True
    aliases: list[str] = []
    category: str = ""
    description: str = ""
    metadata: dict = {}


class EdgeData(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    distance: float = 0.0
    tags: list[str] = []
    accessible: bool = True
    bidirectional: bool = True

    model_config = {"populate_by_name": True}


class RouteStep(BaseModel):
    from_node: str
    from_name: str
    to_node: str
    to_name: str
    distance: float
    floor: int
    floor_change: Optional[dict] = None
    instruction: Optional[str] = None


class RouteResponse(BaseModel):
    success: bool
    start: str
    end: str
    profile: str
    total_distance: float
    estimated_time_seconds: int
    steps: list[RouteStep]
    nodes_visited: list[str]
    error: Optional[str] = None
