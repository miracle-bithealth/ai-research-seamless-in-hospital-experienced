import logging
import traceback

from app.utils.HttpResponseUtils import response_success, response_error
from app.repositories.GraphRepository import graphRepository
from app.repositories.FloorAssetRepository import floorAssetRepository
from core.navigation.manager import GraphManager

logger = logging.getLogger(__name__)


class GraphAdminController:

    def __init__(self):
        self.graph_repo = graphRepository
        self.floor_repo = floorAssetRepository

    async def import_graph(self, payload: dict):
        try:
            building_id = payload.get("building_id")
            if not building_id:
                return response_error(Exception("[WARN] building_id is required"))

            data = {
                "building_name": payload.get("building_name", ""),
                "nodes": payload.get("nodes", []),
                "floors": payload.get("floors", []),
            }
            updated_by = payload.get("updated_by", "admin")

            version = await self.graph_repo.save_graph(building_id, data, updated_by)

            # Hot-reload the in-memory graph
            await GraphManager.reload(building_id)

            # Notify other pods via Redis
            await self._publish_update(building_id)

            return response_success({
                "building_id": building_id,
                "version": version,
                "node_count": len(data["nodes"]),
            })
        except Exception as e:
            traceback.print_exc()
            return response_error(e)

    async def export_graph(self, building_id: str):
        try:
            doc = await self.graph_repo.get_graph(building_id)
            if not doc:
                return response_error(
                    Exception(f"[WARN] Building '{building_id}' not found")
                )

            export = {
                "building_id": doc.get("_id", building_id),
                "version": doc.get("version", 0),
                "building_name": doc.get("building_name", ""),
                "nodes": doc.get("nodes", []),
                "floors": doc.get("floors", []),
            }
            return response_success(export)
        except Exception as e:
            traceback.print_exc()
            return response_error(e)

    async def sync_rooms(self, building_id: str):
        try:
            rooms = await self.graph_repo.get_rooms(building_id)
            doc = await self.graph_repo.get_graph(building_id)
            version = doc.get("version", 0) if doc else 0

            return response_success({
                "building_id": building_id,
                "version": version,
                "rooms": rooms,
            })
        except Exception as e:
            traceback.print_exc()
            return response_error(e)

    async def get_version_history(self, building_id: str, limit: int = 10):
        try:
            versions = await self.graph_repo.get_version_history(building_id, limit)
            entries = []
            for v in versions:
                entries.append({
                    "building_id": building_id,
                    "version": v.get("version", 0),
                    "updated_by": v.get("updated_by", ""),
                    "updated_at": v.get("updated_at", ""),
                    "node_count": len(v.get("nodes", [])),
                })

            return response_success({
                "building_id": building_id,
                "versions": entries,
            })
        except Exception as e:
            traceback.print_exc()
            return response_error(e)

    async def save_floor_asset(self, building_id: str, floor_number: int, svg_s3_url: str):
        try:
            await self.floor_repo.save_floor(building_id, floor_number, svg_s3_url)
            return response_success({
                "building_id": building_id,
                "floor_number": floor_number,
                "svg_s3_url": svg_s3_url,
            })
        except Exception as e:
            traceback.print_exc()
            return response_error(e)

    async def get_floor_assets(self, building_id: str):
        try:
            floors = await self.floor_repo.get_all_floors(building_id)
            return response_success({
                "building_id": building_id,
                "floors": floors,
            })
        except Exception as e:
            traceback.print_exc()
            return response_error(e)

    async def list_buildings(self):
        try:
            buildings = GraphManager.list_buildings()
            return response_success(buildings)
        except Exception as e:
            traceback.print_exc()
            return response_error(e)

    async def _publish_update(self, building_id: str):
        try:
            from config.cache import redis_client
            await redis_client.publish("graph:update", building_id)
        except ImportError:
            logger.debug("Redis not available, skipping graph update broadcast")
        except Exception as e:
            logger.warning("Failed to publish graph update: %s", e)


graphAdminController = GraphAdminController()
