from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class FloorAssetAction(str, Enum):
    UPLOAD = "upload"
    DELETE = "delete"


class FloorAssetPayload(BaseModel):
    building_id: str = Field(..., description="Building identifier")
    floor_number: int = Field(..., description="Floor number")
    svg_s3_url: str = Field(default="", description="S3 URL to the floor SVG file")


class FloorAssetResponse(BaseModel):
    building_id: str
    floor_number: int
    svg_s3_url: str = ""
    updated_at: Optional[str] = None


class GraphVersionEntry(BaseModel):
    building_id: str
    version: int
    updated_by: str = ""
    updated_at: str = ""
    node_count: int = 0


class GraphVersionHistoryResponse(BaseModel):
    building_id: str
    versions: list[GraphVersionEntry] = []


class RoomSyncPayload(BaseModel):
    building_id: str = Field(default="shlv")
    force: bool = Field(default=False, description="Force sync even if version matches")
