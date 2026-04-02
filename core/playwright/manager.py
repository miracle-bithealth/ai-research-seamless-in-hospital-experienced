import asyncio
import logging
from typing import Optional

from .engine import PlaywrightEngine

logger = logging.getLogger(__name__)


class PlaywrightManager:
    """Browser pool lifecycle manager.

    Manages a pool of Playwright browser instances for SVG-to-PNG rendering.
    Uses classmethod pattern consistent with QueueManager.
    """

    _engines: list[PlaywrightEngine] = []
    _browsers: list = []
    _playwright = None
    _pool_size: int = 3
    _lock: Optional[asyncio.Lock] = None

    @classmethod
    async def start(cls, pool_size: int = 3) -> None:
        cls._pool_size = pool_size
        cls._lock = asyncio.Lock()

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning(
                "playwright not installed, PNG rendering disabled"
            )
            return

        cls._playwright = await async_playwright().start()

        for i in range(pool_size):
            try:
                browser = await cls._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-gpu"],
                )
                engine = PlaywrightEngine(browser)
                cls._browsers.append(browser)
                cls._engines.append(engine)
                logger.info("Playwright browser %d/%d launched", i + 1, pool_size)
            except Exception as e:
                logger.error("Failed to launch browser %d: %s", i + 1, e)

    @classmethod
    async def stop(cls) -> None:
        for browser in cls._browsers:
            try:
                await browser.close()
            except Exception:
                pass
        cls._browsers.clear()
        cls._engines.clear()

        if cls._playwright:
            await cls._playwright.stop()
            cls._playwright = None

        logger.info("Playwright pool stopped")

    @classmethod
    async def acquire(cls) -> Optional[PlaywrightEngine]:
        """Get an available engine from the pool."""
        if not cls._engines:
            return None

        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            for engine in cls._engines:
                if not engine.in_use:
                    engine.in_use = True
                    return engine
        return None

    @classmethod
    def release(cls, engine: PlaywrightEngine) -> None:
        engine.in_use = False

    @classmethod
    def pool_size(cls) -> int:
        return len(cls._engines)

    @classmethod
    def available_count(cls) -> int:
        return sum(1 for e in cls._engines if not e.in_use)
