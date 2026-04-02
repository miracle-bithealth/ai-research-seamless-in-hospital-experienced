import datetime
from typing import Dict, Any
from langchain_core.messages import HumanMessage

from core.BaseAgent import BaseAgent
from app.schemas.ChatbotRouterOutputSchema import ChatbotRouterOutput

# Prompt template untuk Primary Chatbot Router
PROMPT_TEMPLATE = """
# Role & Goal
You are a smart router assistant that determines which specialized agent should handle a user's query.
Your primary goal is to analyze the user's query and route it to the appropriate agent:
- **doctor** agent: For queries related to doctors, medical professionals, specialties, doctor availability, finding doctors, etc.
- **qna** agent: For general questions, information queries, and other non-doctor-related questions.

# Persona
- Analytical and precise
- Make routing decisions based on query content
- Be confident but accurate in routing decisions

# Rules & Constraints
1. Route to "doctor" agent if the query is about:
   - Finding doctors
   - Doctor specialties
   - Doctor availability
   - Medical professionals
   - Doctor information or profiles
   - Medical appointments related to doctors

2. Route to "qna" agent if the query is about:
   - General knowledge questions
   - Non-medical information
   - General Q&A that doesn't involve doctors
   - Other topics not related to doctors

3. If unsure, default to "qna" agent

# Context & Resources
- **Current Time:** The reference datetime for all relative date calculations.
  `{time}`

# Process / Steps
1. Analyze the user's query carefully
2. Determine if it's related to doctors/medical professionals or general Q&A
3. Select the appropriate agent type
4. Provide reasoning for the selection
5. Assign confidence score

# Examples
### Example 1: Doctor Query
- **User Query:** "I need to find a cardiologist"
- **Reasoning:** This query is about finding a doctor with a specific specialty (cardiologist), so it should be routed to the doctor agent.
- **Agent Type:** doctor
- **Confidence:** 0.95

### Example 2: General Q&A Query
- **User Query:** "What is the capital of Indonesia?"
- **Reasoning:** This is a general knowledge question unrelated to doctors, so it should be routed to the QNA agent.
- **Agent Type:** qna
- **Confidence:** 0.9

### Example 3: Doctor Availability Query
- **User Query:** "Is Dr. Dian Alhusari available tomorrow?"
- **Reasoning:** This query is about a specific doctor's availability, so it should be routed to the doctor agent.
- **Agent Type:** doctor
- **Confidence:** 0.95

### Example 4: Medical Information Query (Not Doctor-Specific)
- **User Query:** "What are the symptoms of flu?"
- **Reasoning:** This is a general medical information question, not specifically about doctors. Route to QNA agent.
- **Agent Type:** qna
- **Confidence:** 0.85
"""


class ChatbotRouter(BaseAgent):
    """
    Primary chatbot router that determines which agent should handle the query.
    Follows LangGraph pattern: returns decision in state, not directly calling sub-agents.
    """
    
    def __init__(self, llm, **kwargs):
        """
        Initialize ChatbotRouter.
        
        Args:
            llm: Language model for router
            **kwargs: Additional arguments for BaseAgent
        """
        super().__init__(
            llm=llm,
            prompt_template=PROMPT_TEMPLATE,
            output_model=ChatbotRouterOutput,
            use_structured_output=True,
            **kwargs
        )
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute router and return decision in state.
        Follows LangGraph pattern: router only determines decision, doesn't execute sub-agents.
        
        Args:
            state: AgentState with input, decision, response
        
        Returns:
            Dict with updated decision and response
        """
        self.rebind_prompt_variable(
            time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # Extract input from state
        input_data = state.get("input", {})
        user_query = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
        
        # Prepare state for BaseAgent (with messages)
        agent_state = {"messages": [HumanMessage(content=user_query)]}
        
        # Get routing decision
        raw, parsed = await self.arun_chain(state=agent_state)
        
        # Map agent_type to decision string for LangGraph
        decision = parsed.agent_type.value  # "doctor" or "qna"
        
        # Return updated state with decision
        return {
            "decision": decision,
            "input": state.get("input", {}),
            "response": f"Routing to {decision} agent. Reasoning: {parsed.reasoning}"
        }
