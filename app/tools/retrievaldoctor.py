"""
Retrieval Doctor Tool
Tool untuk melakukan retrieval informasi dokter menggunakan MCP tools.
"""

import asyncio
from typing import Dict, Any
from config.mcp import mcpconfig


class RetrievalDoctor:
    """
    Tool untuk retrieval informasi dokter.
    Menggunakan MCP client untuk memanggil tool doctor.
    """
    
    def __init__(self, mcp_client):
        """
        Initialize RetrievalDoctor dengan MCP config.
        
        Args:
            mcp_client: MCP client
        """
        self.mcp_client = mcp_client
    
    async def retrieve_doctor_info(self, query: str, **kwargs) -> str:
        """
        Retrieve informasi dokter berdasarkan query.
        
        Args:
            query: Query untuk mencari informasi dokter
            **kwargs: Additional parameters untuk tool
        
        Returns:
            String berisi hasil retrieval dokter atau error message
        """
        tool_input = {
            "arguments": {"query": query}
        }
        
        # Call tool melalui MCP - all error handling done in tool_call_mcp
        result = await self.mcp_client.tool_call_mcp(
            tool_name="ai-search_doctor",
            tool_input=tool_input
        )
        
        return result
    
    def __call__(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Synchronous wrapper untuk retrieve_doctor_info.
        """
        return asyncio.run(self.retrieve_doctor_info(query, **kwargs))