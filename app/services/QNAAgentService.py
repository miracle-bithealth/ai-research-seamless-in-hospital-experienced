import datetime
from langchain_core.messages import HumanMessage, ToolMessage
from core.BaseAgent import BaseAgent
import time

# Prompt template untuk QNA Agent
PROMPT_TEMPLATE = """
# Role & Goal
You are a helpful Q&A assistant.
Your primary goal is to answer questions accurately and comprehensively 
using the available tools and knowledge base.

# Persona
- Friendly and approachable
- Provide clear and detailed answers
- Use examples when helpful
- Admit when you don't know something

# Rules & Constraints
1. Always provide accurate information
2. Use available tools when needed to get current information
3. If information is not available, clearly state that
4. Structure answers clearly and logically

# Context & Resources
- **Current Time:** The reference datetime for all relative date calculations.
  `{time}`

# Process / Steps
1. Understand the user's question
2. Determine if tools are needed to answer the question
3. Use appropriate tools if necessary
4. Synthesize information and provide a comprehensive answer

# Examples
### Example 1: General Question
- **User Query:** "What is the capital of Indonesia?"
- **Reasoning:** This is a straightforward factual question that can be answered directly.
- **Final Output:** "The capital of Indonesia is Jakarta."

### Example 2: Question Requiring Tool
- **User Query:** "What is the current weather in Jakarta?"
- **Reasoning:** This requires current information, so I should use a weather tool if available.
- **Final Output:** "[Weather information from tool]"
"""


class QNAAgent(BaseAgent):
    """
    Agent untuk menangani pertanyaan umum (Q&A).
    Dapat menggunakan tools yang di-bind untuk mendapatkan informasi.
    """
    
    def __init__(self, llm, tools_mcp, **kwargs):
        """
        Initialize QNAAgent dengan optional tools.
        
        Args:
            llm: Language model untuk agent
            tools: List of tools untuk agent (optional)
            **kwargs: Additional arguments untuk BaseAgent
        """
        super().__init__(
            llm=llm,
            prompt_template=PROMPT_TEMPLATE,
            tools=tools_mcp,
            **kwargs
        )
    
    async def __call__(self, state):
        """
        Execute QNA agent dengan state.
        
        Args:
            state: State dictionary dengan messages atau input
        
        Returns:
            Parsed response dari agent
        """
        try:
            # Extract input from state
            user_query = state.get("input", {}).text
            
            # Bind prompt variables
            self.rebind_prompt_variable(
                time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # Prepare messages
            messages = [HumanMessage(content=user_query)]
            agent_state = {"messages": messages}
            
            # Track tool calls and results
            tool_calls_info = []
            max_iterations = 5
            iteration = 0
            final_answer = None
            
            # Agentic loop
            while iteration < max_iterations:
                iteration += 1
                
                # Call agent chain
                raw_result, parsed_result = await self.arun_chain(state=agent_state)
                
                # Check if LLM is asking to call a tool
                if hasattr(raw_result, 'tool_calls') and raw_result.tool_calls:
                    tool_call = raw_result.tool_calls[0]
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    
                    # Record tool call
                    tool_calls_info.append({
                        "tool": tool_name,
                        "args": tool_args
                    })
                    
                    # Execute the tool
                    tool_to_use = next((t for t in self.tools if t.name == tool_name), None)
                    
                    if tool_to_use:
                        start_time = time.time()
                        # Run tool - error handling done in manual_mcp
                        tool_result = await tool_to_use.ainvoke(tool_args)
                        end_time = time.time()
                        print(f"time tools qna agent taken: {end_time - start_time} seconds")
                        print(f"type tool_result: {type(tool_result)}")
                        print(f"tool_result di qna agent: {tool_result[:100]}")
                        # except Exception as e:
                        #     traceback.print_exc()
                        #     tool_result = f"Error calling tool {tool_name}: {str(e)}"
                        
                        # Add tool result to messages
                        messages.append(raw_result)
                        messages.append(ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call['id']
                        ))
                        
                        # Update agent state
                        agent_state = {"messages": messages}
                    else:
                        final_answer = f"Tool {tool_name} not found"
                        break
                else:
                    # No more tool calls, extract final answer
                    final_answer = raw_result.content if hasattr(raw_result, 'content') and raw_result.content else str(parsed_result)
                    break
            
            if not final_answer:
                final_answer = "No response generated"

            response_data = {
                    "tool_calls": tool_calls_info,
                    "final_answer": final_answer,
            }
            # Format final response
            return {
                "response": response_data,
            }
        except Exception as e:
            raise e