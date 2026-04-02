import datetime
from typing import List
from langchain_core.tools import BaseTool, tool
from langchain_core.messages import HumanMessage, ToolMessage
import traceback

from core.BaseAgent import BaseAgent
from app.tools.retrievaldoctor import RetrievalDoctor

# Prompt template untuk Doctor Agent
PROMPT_TEMPLATE = """
# Role & Goal
You are a medical assistant specialized in providing information about doctors.
Your primary goal is to help users find and understand information about doctors, 
their specialties, availability, and other relevant medical professional details.

# Persona
- Professional and empathetic
- Provide accurate medical information
- Use clear and concise language
- Be helpful in guiding users to find the right doctor

# Rules & Constraints
1. Always provide accurate information based on the retrieved doctor data
2. If information is not available, clearly state that
3. Do not provide medical diagnoses or treatment advice
4. Focus on doctor information: specialties, qualifications, availability, etc.

# Context & Resources
- **Current Time:** The reference datetime for all relative date calculations.
  `{time}`

# Process / Steps
1. Understand the user's query about doctors
2. Use the retrieval_doctor tool to search for relevant doctor information
3. Analyze and format the retrieved information
4. Provide a clear and helpful response to the user

# Examples
### Example 1: Finding a Cardiologist
- **User Query:** "I need to find a cardiologist"
- **Reasoning:** User is looking for a cardiologist. I should use the retrieval_doctor tool to search for doctors with cardiology specialty.
- **Final Output:** "I found several cardiologists available. Here are some options: [doctor information from retrieval]"

### Example 2: Doctor Availability
- **User Query:** "Is Dr. Dian Alhusari available?"
- **Reasoning:** User is asking about specific doctor availability. I should search for this doctor using the retrieval_doctor tool.
- **Final Output:** "Based on the information retrieved, Dr. Dian Alhusari [availability information]"
"""


class DoctorAgent(BaseAgent):
    """
    Agent untuk menangani query terkait informasi dokter.
    Menggunakan retrieval doctor tool untuk mendapatkan informasi dokter.
    """
    
    def __init__(self, llm, mcp_config, **kwargs):
        """
        Initialize DoctorAgent dengan retrieval doctor tool.
        
        Args:
            llm: Language model untuk agent
            **kwargs: Additional arguments untuk BaseAgent
        """
        # Initialize retrieval doctor tool
        retrieval_doctor = RetrievalDoctor(mcp_config)
        
        # Create LangChain tool wrapper
        @tool
        async def retrieval_doctor_tool(query: str):
            """
            Tool untuk mencari informasi dokter berdasarkan query.
            
            Args:
                query: Query untuk mencari informasi dokter (nama, spesialisasi, dll)
            
            Returns:
                String berisi informasi dokter yang ditemukan
            """
            result = await retrieval_doctor.retrieve_doctor_info(query)
            
            return result
        
        # Bind tools ke agent
        tools: List[BaseTool] = [
            retrieval_doctor_tool
            ]
        
        super().__init__(
            llm=llm,
            prompt_template=PROMPT_TEMPLATE,
            tools=tools,
            **kwargs
        )

    async def __call__(self, state):
        """
        Execute doctor agent dengan state.
        
        Args:
            state: State dictionary dengan messages atau input
        
        Returns:
            Final answer string dari agent
        """
        try:
            # Extract input from state
            input_text = state.get("input", {})
            user_query = input_text.text if hasattr(input_text, 'text') else str(input_text)
            
            # Bind prompt variables (required for BaseAgent prompt template)
            self.rebind_prompt_variable(
                time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # Prepare messages for the conversation
            messages = [HumanMessage(content=user_query)]
            agent_state = {"messages": messages}
            
            # 1) Panggil LLM pertama kali
            raw_result, parsed_result = await self.arun_chain(state=agent_state)
            print(f"raw_result: {raw_result}")
            print(f"parsed_result: {parsed_result}")
            
            tool_calls_info = []
            final_answer = None
            
            # 2) Jika LLM minta panggil tool
            if hasattr(raw_result, "tool_calls") and raw_result.tool_calls:
                for tool_call in raw_result.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    print(f"tool_name: {tool_name}")
                    print(f"tool_args: {tool_args}")
                    print(f"tools doctor agent: {self.tools}")

                    tool_to_use = None
                    for tool in self.tools:
                        if tool.name == tool_name:
                            tool_to_use = tool
                            break
                    
                    if tool_to_use:
                        tool_result = await tool_to_use.ainvoke(tool_args)
                        tool_result_str = str(tool_result)
                        print(f"tool_result: {tool_result_str[:100]}")
                        
                        tool_calls_info.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result_preview": tool_result_str[:200],
                        })

                        # Tambahkan ToolMessage ke messages untuk dipakai LLM
                        tool_result_message = ToolMessage(
                            content=tool_result_str,
                            tool_call_id=tool_call["id"],
                        )
                        messages.append(raw_result)
                        messages.append(tool_result_message)
                        agent_state = {"messages": messages}
                
                # 3) Panggil LLM kedua kali untuk ambil final answer
                raw_result2, parsed_result2 = await self.arun_chain(state=agent_state)
                final_answer = raw_result2.content
            else:
                final_answer = raw_result.content
                
            response_data = {
                "tool_calls": tool_calls_info,
                "final_answer": final_answer,
            }
            import json
            response_text = json.dumps(response_data, indent=2, ensure_ascii=False)
            
            return {
                "response": response_text,
                "input": state.get("input", {})
            }
        except Exception as e:
            traceback.print_exc()
            import json
            error_response = {
                "error": str(e),
                "tool_calls": [],
                "final_answer": None
            }
            return {
                "response": json.dumps(error_response, indent=2, ensure_ascii=False),
                "input": state.get("input", {})
            }
