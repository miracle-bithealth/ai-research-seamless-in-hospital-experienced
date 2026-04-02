import json
# from config.manual_mcp import mcpconfig
from config.mcp import mcpconfig


class SampleController:
    def __init__(self):
        # self.tools = mcpconfig.get_tools_for_bind(["ai_search_search", "hope_retriever_query"])
        pass
    async def call(self, text: str):
        result = await mcpconfig.tool_call_mcp("ai-search_doctor", {"arguments": {"query": text}})
        # print("mcp: ", self.tools)

        # # print(self.tools)
        # print("SampleController call result: ", self.tools)
        return result


sampleController = SampleController() 