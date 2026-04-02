import logging
from typing import Optional

from core.navigation.manager import GraphManager

logger = logging.getLogger(__name__)


class GraphQueryHandler:
    """Queries in-memory HospitalGraph for facility info, room listings, location details.

    Used by GraphInfoAgentService to answer "where is X?" or "what's on floor 2?"
    without triggering full navigation.
    """

    def query_locations(self, building_id: str = "shlv", floor: Optional[int] = None) -> dict:
        """List all non-junction locations, optionally filtered by floor."""
        graph = GraphManager.get(building_id)
        if not graph:
            return {"found": False, "message": f"Building '{building_id}' not loaded"}

        locations = graph.get_locations()
        if floor is not None:
            locations = [n for n in locations if n.floor == floor]

        return {
            "found": True,
            "total": len(locations),
            "locations": [
                {
                    "id": n.id,
                    "name": n.name,
                    "floor": n.floor,
                    "type": n.type,
                    "category": n.category,
                    "description": n.description,
                    "aliases": n.aliases,
                }
                for n in sorted(locations, key=lambda n: (n.floor, n.name))
            ],
        }

    def query_location_detail(self, query: str, building_id: str = "shlv") -> dict:
        """Resolve a single location by name/alias and return its details."""
        graph = GraphManager.get(building_id)
        if not graph:
            return {"found": False, "message": f"Building '{building_id}' not loaded"}

        node = graph.resolve_destination(query)
        if node:
            return {
                "found": True,
                "id": node.id,
                "name": node.name,
                "floor": node.floor,
                "type": node.type,
                "category": node.category,
                "description": node.description,
                "aliases": node.aliases,
            }

        locations = graph.get_locations()
        names = ", ".join(n.name for n in sorted(locations, key=lambda n: n.name) if n.name)
        return {
            "found": False,
            "message": f"Lokasi '{query}' tidak ditemukan. Lokasi tersedia: {names}",
        }

    def query_building_info(self, building_id: str = "shlv") -> dict:
        """Return general building metadata."""
        graph = GraphManager.get(building_id)
        if not graph:
            return {"found": False, "message": f"Building '{building_id}' not loaded"}

        locations = graph.get_locations()
        categories = sorted({n.category for n in locations if n.category})

        return {
            "found": True,
            "building_id": graph.building_id,
            "building_name": graph.building_name,
            "floors": graph.floors,
            "total_locations": len(locations),
            "total_nodes": graph.node_count,
            "categories": categories,
        }

    def query_floor_info(self, floor: int, building_id: str = "shlv") -> dict:
        """Return info about a specific floor."""
        graph = GraphManager.get(building_id)
        if not graph:
            return {"found": False, "message": f"Building '{building_id}' not loaded"}

        if floor not in graph.floors:
            return {
                "found": False,
                "message": f"Lantai {floor} tidak tersedia. Lantai yang ada: {graph.floors}",
            }

        floor_locations = [n for n in graph.get_locations() if n.floor == floor]
        categories = sorted({n.category for n in floor_locations if n.category})

        return {
            "found": True,
            "floor": floor,
            "total_locations": len(floor_locations),
            "categories": categories,
            "locations": [
                {"name": n.name, "type": n.type, "category": n.category}
                for n in sorted(floor_locations, key=lambda n: n.name)
            ],
        }


graphQueryHandler = GraphQueryHandler()
