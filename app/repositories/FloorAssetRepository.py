import logging
from datetime import datetime, timezone

from config.mongoDb import MongoDb

logger = logging.getLogger(__name__)

COLLECTION = "floor_assets"


class FloorAssetRepository:

    def __init__(self):
        self.db = MongoDb()

    async def get_floor(self, building_id: str, floor_number: int) -> dict | None:
        return await self.db.find_one(
            {"building_id": building_id, "floor_number": floor_number},
            collection=COLLECTION,
        )

    async def save_floor(self, building_id: str, floor_number: int, svg_s3_url: str) -> None:
        data = {
            "building_id": building_id,
            "floor_number": floor_number,
            "svg_s3_url": svg_s3_url,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.db.update_upsert(
            {"building_id": building_id, "floor_number": floor_number},
            data,
            collection=COLLECTION,
        )
        logger.info("Saved floor asset %s floor %d", building_id, floor_number)

    async def get_all_floors(self, building_id: str) -> list[dict]:
        cursor = self.db.get_cursor(
            {"building_id": building_id},
            sort=[("floor_number", 1)],
            collection=COLLECTION,
        )
        return await cursor.to_list(length=100)

    async def delete_floor(self, building_id: str, floor_number: int) -> None:
        await self.db.delete_many_data(
            {"building_id": building_id, "floor_number": floor_number},
            collection=COLLECTION,
        )
        logger.info("Deleted floor asset %s floor %d", building_id, floor_number)


floorAssetRepository = FloorAssetRepository()
