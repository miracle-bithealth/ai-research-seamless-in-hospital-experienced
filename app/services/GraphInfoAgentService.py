import datetime
import json
import traceback
from langchain_core.tools import BaseTool, tool
from langchain_core.messages import HumanMessage, ToolMessage

from core.BaseAgent import BaseAgent
from app.tools.GraphQuery import graphQueryHandler
from core.navigation.prompt import GRAPH_INFO_PROMPT


class GraphInfoAgent(BaseAgent):

    def __init__(self, llm, **kwargs):
        @tool
        def graph_query_locations(building_id: str = "shlv", floor: int = None) -> str:
            """List all facilities and rooms in the hospital, optionally filtered by floor number.
            Use when user asks 'what is available' or 'what is on floor X'.
            """
            result = graphQueryHandler.query_locations(building_id, floor)
            return json.dumps(result, ensure_ascii=False)

        @tool
        def graph_query_location_detail(query: str, building_id: str = "shlv") -> str:
            """Look up details about a specific location by name or alias.
            Use when user asks about a specific facility like 'farmasi' or 'toilet'.
            """
            result = graphQueryHandler.query_location_detail(query, building_id)
            return json.dumps(result, ensure_ascii=False)

        @tool
        def graph_query_building_info(building_id: str = "shlv") -> str:
            """Get general hospital building information: floors, total locations, categories.
            Use when user asks general questions about the hospital.
            """
            result = graphQueryHandler.query_building_info(building_id)
            return json.dumps(result, ensure_ascii=False)

        @tool
        def graph_query_floor_info(floor: int, building_id: str = "shlv") -> str:
            """Get information about a specific floor: what facilities are there, categories.
            Use when user asks 'what is on floor X' or 'lantai X ada apa'.
            """
            result = graphQueryHandler.query_floor_info(floor, building_id)
            return json.dumps(result, ensure_ascii=False)

        tools: list[BaseTool] = [
            graph_query_locations,
            graph_query_location_detail,
            graph_query_building_info,
            graph_query_floor_info,
        ]

        super().__init__(
            llm=llm,
            prompt_template=GRAPH_INFO_PROMPT,
            tools=tools,
            **kwargs
        )

    async def __call__(self, state):
        try:
            input_data = state.get("input", {})
            user_query = input_data.get("query", "") if isinstance(input_data, dict) else str(input_data)
            building_id = state.get("building_id", "shlv")

            self.rebind_prompt_variable(
                time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                building_id=building_id,
            )

            messages = [HumanMessage(content=user_query)]
            agent_state = {"messages": messages}

            tool_calls_info = []
            final_answer = None

            max_iterations = 6
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                raw_result, parsed_result = await self.arun_chain(state=agent_state)

                if hasattr(raw_result, "tool_calls") and raw_result.tool_calls:
                    messages.append(raw_result)

                    for tool_call in raw_result.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]

                        tool_to_use = next(
                            (t for t in self.tools if t.name == tool_name), None
                        )

                        if tool_to_use:
                            if "building_id" not in tool_args:
                                tool_args["building_id"] = building_id

                            tool_result = await tool_to_use.ainvoke(tool_args)
                            tool_result_str = str(tool_result)

                            tool_calls_info.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "result_preview": tool_result_str[:300],
                            })

                            messages.append(ToolMessage(
                                content=tool_result_str,
                                tool_call_id=tool_call["id"],
                            ))

                    agent_state = {"messages": messages}
                else:
                    final_answer = raw_result.content if hasattr(raw_result, "content") else str(raw_result)
                    break

            if not final_answer:
                final_answer = raw_result.content if hasattr(raw_result, "content") else "Informasi tidak tersedia."

            response_data = {
                "tool_calls": tool_calls_info,
                "final_answer": final_answer,
            }

            return {
                "response": json.dumps(response_data, indent=2, ensure_ascii=False),
                "input": state.get("input", {}),
            }
        except Exception as e:
            traceback.print_exc()
            error_response = {
                "error": str(e),
                "tool_calls": [],
                "final_answer": None,
            }
            return {
                "response": json.dumps(error_response, indent=2, ensure_ascii=False),
                "input": state.get("input", {}),
            }
