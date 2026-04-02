import asyncio
import logging
from typing import Optional

from .graph import HospitalGraph

logger = logging.getLogger(__name__)


class GraphManager:
    """Manages in-memory HospitalGraph instances per building.

    Loads from MongoDB via GraphRepository, supports hot reload
    through Redis pub/sub on graph:update channel.
    """

    _graphs: dict[str, HospitalGraph] = {}
    _repository = None
    _listener_task: Optional[asyncio.Task] = None

    @classmethod
    def set_repository(cls, repository) -> None:
        cls._repository = repository

    @classmethod
    async def load_all_buildings(cls) -> None:
        if cls._repository is None:
            logger.warning("GraphManager: no repository set, skipping load")
            return

        docs = await cls._repository.get_all_graphs()
        for doc in docs:
            building_id = doc.get("_id", "")
            if not building_id:
                continue
            try:
                graph = HospitalGraph.from_mongo_doc(doc)
                cls._graphs[building_id] = graph
                logger.info(
                    "Loaded graph: %s (%d nodes, %d edges)",
                    building_id, graph.node_count, graph.edge_count,
                )
            except Exception as e:
                logger.error("Failed to load graph %s: %s", building_id, e)

    @classmethod
    def get(cls, building_id: str) -> Optional[HospitalGraph]:
        return cls._graphs.get(building_id)

    @classmethod
    def get_default(cls) -> Optional[HospitalGraph]:
        if cls._graphs:
            return next(iter(cls._graphs.values()))
        return None

    @classmethod
    async def reload(cls, building_id: str) -> None:
        """Re-read from MongoDB, build new graph, atomic pointer swap."""
        if cls._repository is None:
            return

        doc = await cls._repository.get_graph(building_id)
        if doc is None:
            logger.warning("Graph not found for reload: %s", building_id)
            return

        graph = HospitalGraph.from_mongo_doc(doc)
        cls._graphs[building_id] = graph
        logger.info(
            "Reloaded graph: %s (%d nodes, %d edges)",
            building_id, graph.node_count, graph.edge_count,
        )

    @classmethod
    def register(cls, building_id: str, graph: HospitalGraph) -> None:
        """Register a graph directly (for testing or seed scripts)."""
        cls._graphs[building_id] = graph

    @classmethod
    async def start_listener(cls) -> None:
        """Start Redis pub/sub listener for graph:update channel."""
        try:
            from config.cache import redis_client
        except ImportError:
            logger.warning("Redis not available, graph sync disabled")
            return

        async def _listen():
            try:
                pubsub = redis_client.pubsub()
                await pubsub.subscribe("graph:update")
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    building_id = message["data"]
                    if isinstance(building_id, bytes):
                        building_id = building_id.decode()
                    logger.info("Graph update signal: %s", building_id)
                    await cls.reload(building_id)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("Graph listener error: %s", e)

        cls._listener_task = asyncio.create_task(_listen())

    @classmethod
    async def stop_listener(cls) -> None:
        if cls._listener_task and not cls._listener_task.done():
            cls._listener_task.cancel()
            try:
                await asyncio.wait_for(cls._listener_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            cls._listener_task = None

    @classmethod
    def list_buildings(cls) -> list[dict]:
        return [
            {
                "building_id": g.building_id,
                "building_name": g.building_name,
                "floors": g.floors,
                "node_count": g.node_count,
                "edge_count": g.edge_count,
            }
            for g in cls._graphs.values()
        ]

    @classmethod
    def clear(cls) -> None:
        """Clear all loaded graphs. Primarily for testing."""
        cls._graphs.clear()
