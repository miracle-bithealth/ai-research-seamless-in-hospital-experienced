import logging
import aiohttp
from typing import Optional

from core.CircuitBreaker import CircuitBreaker
from core.navigation.manager import GraphManager

logger = logging.getLogger(__name__)


class AISearchNavigateHandler:
    """Resolves natural language location to node UUID via AI Search REST API.

    Falls back to local HospitalGraph.resolve_destination() when the
    circuit breaker is OPEN or AI Search is not configured.
    """

    def __init__(self):
        self._base_url: Optional[str] = None
        self._timeout: float = 5.0
        self._circuit = CircuitBreaker(
            name="ai_search_navigate",
            failure_threshold=3,
            recovery_timeout=30.0,
            fallback=None,
        )
        self._load_config()

    def _load_config(self):
        try:
            from config.setting import env
            self._base_url = getattr(env, "AI_SEARCH_BASE_URL", None)
            self._timeout = getattr(env, "AI_SEARCH_TIMEOUT_S", 5.0) or 5.0
        except Exception:
            pass

    async def resolve(self, query: str, building_id: str = "shlv") -> dict:
        """Resolve a location query to a node ID.

        Tries AI Search first (with circuit breaker), falls back to local graph search.
        """
        if self._base_url:
            try:
                result = await self._circuit.call(
                    self._search_remote, query, building_id
                )
                if result and result.get("found"):
                    return result
            except Exception as e:
                logger.warning("AI Search failed, using local fallback: %s", e)

        return self._search_local(query, building_id)

    async def _search_remote(self, query: str, building_id: str) -> dict:
        url = f"{self._base_url}/search"
        payload = {"query": query, "building_id": building_id}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"AI Search returned {resp.status}")
                data = await resp.json()
                return data

    def _search_local(self, query: str, building_id: str) -> dict:
        graph = GraphManager.get(building_id)
        if not graph:
            return {"found": False, "message": f"Building '{building_id}' not loaded"}

        node = graph.resolve_destination(query)
        if node:
            return {
                "found": True,
                "node_id": node.id,
                "name": node.name,
                "floor": node.floor,
                "type": node.type,
                "aliases": node.aliases,
                "source": "local",
            }

        locations = graph.get_locations()
        names = ", ".join(n.name for n in sorted(locations, key=lambda n: n.name) if n.name)
        return {
            "found": False,
            "message": f"Lokasi '{query}' tidak ditemukan. Lokasi tersedia: {names}",
        }


aiSearchHandler = AISearchNavigateHandler()
