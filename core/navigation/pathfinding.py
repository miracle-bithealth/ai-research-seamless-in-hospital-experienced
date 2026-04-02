import heapq
import math
from typing import Optional

from .graph import HospitalGraph
from .models import RouteResponse, RouteStep, EdgeData

WALKING_SPEED_MS = 1.4
MAP_RATIO = 20.0
FLOOR_PENALTY = 30.0


def _edge_weight(edge: EdgeData, distance: float, profile: str) -> Optional[float]:
    if profile == "default":
        return distance

    if profile == "wheelchair":
        if not edge.accessible:
            return None
        if "stairs" in edge.tags:
            return None
        return distance

    if profile == "elderly":
        w = distance
        if "stairs" in edge.tags:
            w *= 3.0
        real_meters = distance / MAP_RATIO
        if real_meters > 50:
            w *= 1.5
        return w

    if profile == "emergency":
        return distance

    return distance


def _heuristic(graph: HospitalGraph, node_id: str, goal_id: str) -> float:
    a = graph.nodes[node_id]
    b = graph.nodes[goal_id]
    dx = a.x - b.x
    dy = a.y - b.y
    euclidean = math.sqrt(dx * dx + dy * dy)
    floor_diff = abs(a.floor - b.floor)
    return euclidean + floor_diff * FLOOR_PENALTY


def astar(
    graph: HospitalGraph,
    start_id: str,
    goal_id: str,
    profile: str = "default",
) -> Optional[list[str]]:
    """A* shortest path. Returns node ID list from start to goal, or None."""
    if start_id not in graph.nodes or goal_id not in graph.nodes:
        return None

    if start_id == goal_id:
        return [start_id]

    counter = 0
    open_set: list[tuple[float, int, str]] = []
    heapq.heappush(open_set, (0.0, counter, start_id))

    came_from: dict[str, str] = {}
    g_score: dict[str, float] = {start_id: 0.0}
    closed: set[str] = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == goal_id:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        if current in closed:
            continue
        closed.add(current)

        for neighbor_id, distance, edge in graph.get_neighbors(current):
            if neighbor_id in closed:
                continue

            weight = _edge_weight(edge, distance, profile)
            if weight is None:
                continue

            tentative_g = g_score[current] + weight

            if tentative_g < g_score.get(neighbor_id, math.inf):
                came_from[neighbor_id] = current
                g_score[neighbor_id] = tentative_g
                f_score = tentative_g + _heuristic(graph, neighbor_id, goal_id)
                counter += 1
                heapq.heappush(open_set, (f_score, counter, neighbor_id))

    return None


def find_route(
    graph: HospitalGraph,
    start_id: str,
    goal_id: str,
    profile: str = "default",
) -> RouteResponse:
    start_node = graph.get_node(start_id)
    end_node = graph.get_node(goal_id)

    if not start_node:
        return RouteResponse(
            success=False, start=start_id, end=goal_id, profile=profile,
            total_distance=0, estimated_time_seconds=0, steps=[], nodes_visited=[],
            error=f"Start node '{start_id}' not found",
        )

    if not end_node:
        return RouteResponse(
            success=False, start=start_id, end=goal_id, profile=profile,
            total_distance=0, estimated_time_seconds=0, steps=[], nodes_visited=[],
            error=f"End node '{goal_id}' not found",
        )

    path = astar(graph, start_id, goal_id, profile)

    if path is None:
        return RouteResponse(
            success=False, start=start_id, end=goal_id, profile=profile,
            total_distance=0, estimated_time_seconds=0, steps=[], nodes_visited=[],
            error="No route found between the specified nodes",
        )

    steps: list[RouteStep] = []
    total_distance = 0.0

    for i in range(len(path) - 1):
        from_id = path[i]
        to_id = path[i + 1]
        from_node = graph.nodes[from_id]
        to_node = graph.nodes[to_id]

        dist = graph.euclidean_distance(from_id, to_id)
        total_distance += dist

        floor_change = None
        if from_node.floor != to_node.floor:
            via = "corridor"
            if to_node.type == "elevator" or from_node.type == "elevator":
                via = "elevator"
            elif to_node.type == "stairs" or from_node.type == "stairs":
                via = "stairs"
            floor_change = {
                "from": from_node.floor,
                "to": to_node.floor,
                "via": via,
            }

        steps.append(RouteStep(
            from_node=from_id,
            from_name=from_node.name,
            to_node=to_id,
            to_name=to_node.name,
            distance=round(dist, 1),
            floor=from_node.floor,
            floor_change=floor_change,
            instruction=None,
        ))

    real_distance_m = total_distance / MAP_RATIO
    walking_time_s = int(real_distance_m / WALKING_SPEED_MS)

    return RouteResponse(
        success=True,
        start=start_id,
        end=goal_id,
        profile=profile,
        total_distance=round(real_distance_m, 1),
        estimated_time_seconds=walking_time_s,
        steps=steps,
        nodes_visited=path,
    )
