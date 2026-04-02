import json
import traceback
import uuid

from app.generative import manager as AiManager
from app.utils.HttpResponseUtils import response_success, response_error
from app.services.NavigationRouterService import NavigationRouter
from app.services.NavigationAgentService import NavigationAgent
from app.services.GuideMeAgentService import GuideMeAgent
from app.services.GraphInfoAgentService import GraphInfoAgent
from app.schemas.NavigationStateSchema import NavigationState
from app.schemas.WebSocketMessageSchema import WSRouteMeta, WSRouteStep, WSRouteComplete, WSError
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END
from typing import Dict


class NavigationController:

    def __init__(self):
        self.llm = AiManager.gemini_mini()
        self.router = NavigationRouter(llm=self.llm)
        self.nav_agent = NavigationAgent(llm=self.llm)
        self.guide_me_agent = GuideMeAgent(llm=self.llm)
        self.graph_info_agent = GraphInfoAgent(llm=self.llm)
        self.build_graph(checkpoint=InMemorySaver())

    async def nav_agent_node(self, state: NavigationState) -> Dict:
        try:
            result = await self.nav_agent(state)
            return result
        except Exception as e:
            traceback.print_exc()
            return {"response": json.dumps({"error": str(e)})}

    async def info_node(self, state: NavigationState) -> Dict:
        try:
            result = await self.graph_info_agent(state)
            return result
        except Exception as e:
            traceback.print_exc()
            return {"response": json.dumps({"error": str(e)})}

    async def guide_me_node(self, state: NavigationState) -> Dict:
        try:
            result = await self.guide_me_agent(state)
            return result
        except Exception as e:
            traceback.print_exc()
            return {"response": json.dumps({"error": str(e)})}

    async def fallback_node(self, state: NavigationState) -> Dict:
        return {
            "response": json.dumps({
                "final_answer": "Maaf, saya hanya bisa membantu navigasi dan informasi fasilitas rumah sakit. Silakan tanyakan arah ke suatu lokasi atau informasi fasilitas."
            }),
            "input": state.get("input", {}),
        }

    def build_graph(self, checkpoint=None):
        workflow = StateGraph(NavigationState)

        workflow.add_node("router", self.router)
        workflow.add_node("nav_agent", self.nav_agent_node)
        workflow.add_node("guide_me", self.guide_me_node)
        workflow.add_node("graph_info", self.info_node)
        workflow.add_node("fallback", self.fallback_node)

        workflow.set_entry_point("router")

        workflow.add_conditional_edges(
            "router",
            lambda state: state.get("decision", "fallback"),
            {
                "navigation": "nav_agent",
                "guide_me": "guide_me",
                "info": "graph_info",
                "fallback": "fallback",
            }
        )

        workflow.add_edge("nav_agent", END)
        workflow.add_edge("guide_me", END)
        workflow.add_edge("graph_info", END)
        workflow.add_edge("fallback", END)

        graph = workflow.compile(checkpointer=checkpoint)
        self.graph = graph
        return graph

    async def start_navigating(self, input_data: dict):
        try:
            initial_state = NavigationState(
                input=input_data,
                decision="",
                building_id=input_data.get("building_id", "shlv"),
                current_location=input_data.get("current_location"),
                current_floor=input_data.get("current_floor"),
                output_format=input_data.get("output_format", "svg"),
                route_data=None,
                segments=None,
                rendered_images=None,
                instructions=None,
                response="",
            )
            config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            result = await self.graph.ainvoke(initial_state, config=config)
            return response_success(result["response"])
        except Exception as e:
            traceback.print_exc()
            return response_error(e)

    def _parse_json_field(self, value):
        """Parse a field that might be a JSON string or already a Python object."""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    async def handle_websocket(self, websocket):
        from starlette.websockets import WebSocketState
        await websocket.accept()

        try:
            while True:
                data = await websocket.receive_json()
                correlation_id = str(uuid.uuid4())

                try:
                    initial_state = NavigationState(
                        input=data,
                        decision="",
                        building_id=data.get("building_id", "shlv"),
                        current_location=data.get("current_location"),
                        current_floor=data.get("current_floor"),
                        output_format=data.get("output_format", "svg"),
                        route_data=None,
                        segments=None,
                        rendered_images=None,
                        instructions=None,
                        response="",
                    )
                    config = {"configurable": {"thread_id": correlation_id}}
                    result = await self.graph.ainvoke(initial_state, config=config)

                    route_data = self._parse_json_field(result.get("route_data"))
                    rendered = self._parse_json_field(result.get("rendered_images")) or []
                    instructions = result.get("instructions") or []

                    if route_data and route_data.get("success"):
                        floors_visited = route_data.get("floors_visited", [])
                        meta = WSRouteMeta(
                            total_steps=len(rendered),
                            total_distance_m=route_data.get("total_distance", 0),
                            estimated_time_s=int(route_data.get("estimated_time_seconds", 0)),
                            floors_involved=floors_visited,
                            correlation_id=correlation_id,
                        )
                        await websocket.send_json(meta.model_dump())

                        for i, seg in enumerate(rendered):
                            instruction = instructions[i] if i < len(instructions) else ""
                            step = WSRouteStep(
                                step=i + 1,
                                total_steps=len(rendered),
                                floor=seg.get("floor", 1),
                                instruction=instruction,
                                image_url=seg.get("image_url"),
                                svg_data=seg.get("svg_data"),
                                distance_m=seg.get("distance_m", 0),
                                landmarks=seg.get("landmarks", []),
                            )
                            await websocket.send_json(step.model_dump())

                        dest_name = data.get("query", "tujuan")
                        complete = WSRouteComplete(
                            destination=dest_name,
                            message=f"Anda telah sampai di {dest_name}.",
                        )
                        await websocket.send_json(complete.model_dump())
                    else:
                        response_text = result.get("response") or ""
                        msg = ""
                        try:
                            parsed = json.loads(response_text)
                            msg = parsed.get("final_answer") or ""
                        except (json.JSONDecodeError, TypeError):
                            msg = response_text

                        if not msg:
                            msg = "Lokasi tidak ditemukan. Silakan coba dengan nama lain."

                        error = WSError(code=404, message=msg)
                        await websocket.send_json(error.model_dump())

                except Exception as e:
                    traceback.print_exc()
                    error = WSError(code=500, message=str(e))
                    await websocket.send_json(error.model_dump())

        except Exception:
            pass
        finally:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()


navigationController = NavigationController()
