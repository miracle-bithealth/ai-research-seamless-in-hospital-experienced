import logging
import aiohttp
from typing import Optional

from core.CircuitBreaker import CircuitBreaker

logger = logging.getLogger(__name__)


class VirtualQueueHandler:
    """Resolves queue number to destination via Virtual Queue REST API.

    Used in the "Guide Me" flow: patient provides a queue number (e.g. B-045),
    this handler looks up which room/counter they should go to.
    """

    def __init__(self):
        self._base_url: Optional[str] = None
        self._timeout: float = 5.0
        self._circuit = CircuitBreaker(
            name="virtual_queue",
            failure_threshold=3,
            recovery_timeout=30.0,
            fallback=None,
        )
        self._load_config()

    def _load_config(self):
        try:
            from config.setting import env
            self._base_url = getattr(env, "VIRTUAL_QUEUE_BASE_URL", None)
        except Exception:
            pass

    async def get_queue_destination(self, queue_number: str, building_id: str = "shlv") -> dict:
        """Look up queue number and return the destination info.

        Returns dict with: found, queue_number, destination_name, destination_id,
        estimated_wait_minutes, counter, status.
        """
        if not self._base_url:
            return {
                "found": False,
                "queue_number": queue_number,
                "message": "Virtual Queue service is not configured",
            }

        try:
            result = await self._circuit.call(
                self._query_remote, queue_number, building_id
            )
            return result
        except Exception as e:
            logger.warning("Virtual Queue lookup failed: %s", e)
            return {
                "found": False,
                "queue_number": queue_number,
                "message": f"Gagal mengambil data antrian: {e}",
            }

    async def _query_remote(self, queue_number: str, building_id: str) -> dict:
        url = f"{self._base_url}/queue/lookup"
        payload = {"queue_number": queue_number, "building_id": building_id}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Virtual Queue returned {resp.status}")
                data = await resp.json()
                return data


virtualQueueHandler = VirtualQueueHandler()
