from pydantic import BaseModel, Field
from typing import Optional


class GraphImportPayload(BaseModel):
    building_id: str = Field(..., description="Unique building identifier")
    building_name: str = Field(default="", description="Human-readable building name")
    nodes: list[dict] = Field(default_factory=list)
    floors: list[int] = Field(default_factory=list)


class GraphExportResponse(BaseModel):
    building_id: str
    version: int = 1
    nodes: list[dict] = []
    floors: list[int] = []


class RoomSyncResponse(BaseModel):
    building_id: str
    version: int = 1
    rooms: list[dict] = []
