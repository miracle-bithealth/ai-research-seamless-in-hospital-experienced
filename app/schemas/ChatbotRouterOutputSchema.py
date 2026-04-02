from pydantic import BaseModel, Field
from enum import Enum


class AgentType(str, Enum):
    """Enum for agent types."""
    DOCTOR = "doctor"
    QNA = "qna"


class ChatbotRouterOutput(BaseModel):
    """
    Output schema for the primary chatbot router.
    Determines which agent should handle the user query.
    """
    
    agent_type: AgentType = Field(
        ...,
        description="Which agent should handle the query: 'doctor' for the Doctor agent, 'qna' for the QnA agent."
    )
    
    reasoning: str = Field(
        ...,
        description="Reason for choosing the selected agent."
    )
    
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for the routing decision (0.0 - 1.0)."
    )