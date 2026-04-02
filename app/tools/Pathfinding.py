from core.navigation.manager import GraphManager
from core.navigation.pathfinding import find_route


class PathfindingHandler:
    """Wraps core/navigation/pathfinding.find_route() for tool usage."""

    def execute(
        self,
        from_node: str,
        to_node: str,
        building_id: str = "shlv",
        profile: str = "default",
    ) -> dict:
        graph = GraphManager.get(building_id)
        if not graph:
            return {"success": False, "error": f"Building '{building_id}' not loaded"}

        route = find_route(graph, from_node, to_node, profile)
        data = route.model_dump()

        if route.success:
            same_floor = not any(s.floor_change for s in route.steps)

            # Enrich junction names with nearby landmarks
            for step in data["steps"]:
                for key in ("from_node", "to_node"):
                    node = graph.get_node(step[key])
                    if node and node.type == "junction":
                        landmark = self._get_landmark(graph, step[key], same_floor)
                        if landmark:
                            name_key = "from_name" if key == "from_node" else "to_name"
                            step[name_key] = f"dekat {landmark}"

            floors_visited = []
            for step_obj in route.steps:
                fn = graph.get_node(step_obj.from_node)
                tn = graph.get_node(step_obj.to_node)
                if fn and fn.floor not in floors_visited:
                    floors_visited.append(fn.floor)
                if tn and tn.floor not in floors_visited:
                    floors_visited.append(tn.floor)
            data["floors_visited"] = floors_visited

        return data

    def _get_landmark(self, graph, node_id: str, same_floor: bool) -> str | None:
        vertical_keywords = {"eskalator", "escalator", "lift", "elevator", "tangga", "stairs"}
        neighbors = graph.get_neighbors(node_id)
        rooms = []
        others = []

        for n_id, _, _ in neighbors:
            n = graph.get_node(n_id)
            if not n or n.type == "junction":
                continue
            if same_floor and n.type in {"elevator", "stairs", "escalator"}:
                continue
            name_lower = n.name.lower()
            if same_floor and any(kw in name_lower for kw in vertical_keywords):
                continue
            if n.type == "room":
                rooms.append(n.name)
            else:
                others.append(n.name)

        return rooms[0] if rooms else (others[0] if others else None)


pathfindingHandler = PathfindingHandler()
