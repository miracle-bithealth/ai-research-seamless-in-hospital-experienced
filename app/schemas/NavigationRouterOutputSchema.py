from pydantic import BaseModel, Field
from enum import Enum


class NavigationIntent(str, Enum):
    NAVIGATION = "navigation"
    GUIDE_ME = "guide_me"
    INFO = "info"
    FALLBACK = "fallback"


class NavigationRouterOutput(BaseModel):
    intent: NavigationIntent = Field(
        ...,
        description="Classified user intent: navigation, guide_me, info, or fallback"
    )

    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification (0.0 - 1.0)"
    )

    reasoning: str = Field(
        ...,
        description="Brief reasoning for the classification decision"
    )
