from typing import Optional, TypedDict


class NavigationState(TypedDict):
    input: dict
    decision: str
    building_id: str
    current_location: Optional[str]
    current_floor: Optional[int]
    output_format: str
    route_data: Optional[dict]
    segments: Optional[list]
    rendered_images: Optional[list]
    instructions: Optional[list]
    response: str
