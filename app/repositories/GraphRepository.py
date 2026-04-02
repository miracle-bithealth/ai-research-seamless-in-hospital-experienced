import logging
from datetime import datetime, timezone

from config.mongoDb import MongoDb

logger = logging.getLogger(__name__)

COLLECTION_GRAPH = "graph_data"
COLLECTION_VERSIONS = "graph_versions"


class GraphRepository:

    def __init__(self):
        self.db = MongoDb()

    async def get_graph(self, building_id: str) -> dict | None:
        return await self.db.find_one(
            {"_id": building_id},
            collection=COLLECTION_GRAPH,
        )

    async def get_all_graphs(self) -> list[dict]:
        cursor = self.db.get_cursor({}, collection=COLLECTION_GRAPH)
        return await cursor.to_list(length=100)

    async def save_graph(self, building_id: str, data: dict, updated_by: str = "system") -> int:
        existing = await self.get_graph(building_id)
        version = (existing.get("version", 0) + 1) if existing else 1

        # Archive current version before overwrite
        if existing:
            archive = {**existing, "archived_at": datetime.now(timezone.utc).isoformat()}
            archive.pop("_id", None)
            archive["building_id"] = building_id
            await self.db.update_upsert(
                {"building_id": building_id, "version": existing.get("version", 0)},
                archive,
                collection=COLLECTION_VERSIONS,
            )

        data["_id"] = building_id
        data["version"] = version
        data["updated_by"] = updated_by
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        await self.db.update_upsert(
            {"_id": building_id},
            data,
            collection=COLLECTION_GRAPH,
        )
        logger.info("Saved graph %s version %d", building_id, version)
        return version

    async def get_rooms(self, building_id: str) -> list[dict]:
        doc = await self.get_graph(building_id)
        if not doc:
            return []
        return [
            n for n in doc.get("nodes", [])
            if n.get("type") != "junction"
        ]

    async def get_version_history(self, building_id: str, limit: int = 10) -> list[dict]:
        cursor = self.db.get_cursor(
            {"building_id": building_id},
            sort=[("version", -1)],
            limit=limit,
            collection=COLLECTION_VERSIONS,
        )
        return await cursor.to_list(length=limit)


graphRepository = GraphRepository()
