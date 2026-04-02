import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from .graph import HospitalGraph
from .manager import GraphManager
from .models import RouteResponse
from .pathfinding import find_route, MAP_RATIO
from .segmenter import RouteSegment, RouteSegmenter
from .renderer import SegmentRenderer

logger = logging.getLogger(__name__)


@dataclass
class NavigationResult:
    success: bool
    route: Optional[RouteResponse] = None
    segments: list[RouteSegment] = field(default_factory=list)
    rendered_svgs: list[str] = field(default_factory=list)
    destination_node: Optional[str] = None
    destination_name: Optional[str] = None
    error: Optional[str] = None


class NavigationEngine:
    """Orchestrates the full navigation pipeline: resolve -> route -> segment -> render.

    This is the core engine called by tools and agents. It does not handle
    LLM instruction generation or WebSocket streaming -- those belong in the
    app/services layer.
    """

    def __init__(
        self,
        floor_svg_dir: str = "data/floors",
        default_building: str = "shlv",
    ) -> None:
        self._segmenter = RouteSegmenter()
        self._renderer = SegmentRenderer()
        self._floor_svg_dir = floor_svg_dir
        self._default_building = default_building
        self._svg_cache: dict[str, str] = {}

    def navigate(
        self,
        start_id: str,
        destination_query: str,
        building_id: Optional[str] = None,
        profile: str = "default",
        render: bool = True,
    ) -> NavigationResult:
        """Full pipeline: resolve destination by name, then route + segment + render."""
        graph = self._get_graph(building_id)
        if graph is None:
            return NavigationResult(
                success=False,
                error=f"Building '{building_id or self._default_building}' not loaded",
            )

        node = graph.resolve_destination(destination_query)
        if node is None:
            return NavigationResult(
                success=False,
                error=f"Could not resolve destination: '{destination_query}'",
            )

        return self.route(
            start_id=start_id,
            end_id=node.id,
            building_id=building_id,
            profile=profile,
            render=render,
            _resolved_name=node.name,
        )

    def route(
        self,
        start_id: str,
        end_id: str,
        building_id: Optional[str] = None,
        profile: str = "default",
        render: bool = True,
        _resolved_name: Optional[str] = None,
    ) -> NavigationResult:
        """Route between two known node IDs: pathfind -> segment -> render."""
        graph = self._get_graph(building_id)
        if graph is None:
            return NavigationResult(
                success=False,
                error=f"Building '{building_id or self._default_building}' not loaded",
            )

        route_resp = find_route(graph, start_id, end_id, profile)
        if not route_resp.success:
            return NavigationResult(
                success=False,
                route=route_resp,
                error=route_resp.error,
            )

        end_node = graph.get_node(end_id)
        dest_name = _resolved_name or (end_node.name if end_node else "")

        segments = self._segmenter.segment(graph, route_resp.nodes_visited, profile)

        rendered_svgs: list[str] = []
        if render and segments:
            bid = building_id or self._default_building
            base_svgs = self._load_floor_svgs(bid, graph.floors)
            if base_svgs:
                rendered_svgs = self._renderer.render_all_segments(
                    base_svgs, segments, graph
                )

        return NavigationResult(
            success=True,
            route=route_resp,
            segments=segments,
            rendered_svgs=rendered_svgs,
            destination_node=end_id,
            destination_name=dest_name,
        )

    def resolve(
        self,
        query: str,
        building_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Resolve a destination query to a node. Returns dict with id/name/floor or None."""
        graph = self._get_graph(building_id)
        if graph is None:
            return None

        node = graph.resolve_destination(query)
        if node is None:
            return None

        return {"id": node.id, "name": node.name, "floor": node.floor}

    def get_locations(self, building_id: Optional[str] = None) -> list[dict]:
        """List all navigable locations (rooms, not junctions)."""
        graph = self._get_graph(building_id)
        if graph is None:
            return []

        return [
            {
                "id": n.id,
                "name": n.name,
                "floor": n.floor,
                "category": n.category,
            }
            for n in graph.get_locations()
        ]

    def segment_distance_meters(self, segment: RouteSegment) -> float:
        return round(segment.distance / MAP_RATIO, 1)

    def segment_distance_steps(self, segment: RouteSegment) -> int:
        """Approximate step count. Average stride ~0.65m."""
        meters = segment.distance / MAP_RATIO
        return max(1, round(meters / 0.65))

    # -- Internal --

    def _get_graph(self, building_id: Optional[str] = None) -> Optional[HospitalGraph]:
        bid = building_id or self._default_building
        graph = GraphManager.get(bid)
        if graph is None:
            graph = GraphManager.get_default()
        return graph

    def _load_floor_svgs(
        self, building_id: str, floors: list[int]
    ) -> dict[int, str]:
        result: dict[int, str] = {}

        for floor in floors:
            cache_key = f"{building_id}:{floor}"
            if cache_key in self._svg_cache:
                result[floor] = self._svg_cache[cache_key]
                continue

            svg_path = os.path.join(self._floor_svg_dir, building_id, f"{floor}.svg")
            try:
                with open(svg_path, "r", encoding="utf-8") as f:
                    svg_content = f.read()
                self._svg_cache[cache_key] = svg_content
                result[floor] = svg_content
            except FileNotFoundError:
                logger.warning("Floor SVG not found: %s", svg_path)
            except Exception as e:
                logger.error("Failed to read floor SVG %s: %s", svg_path, e)

        return result

    def clear_svg_cache(self) -> None:
        self._svg_cache.clear()
