import logging

logger = logging.getLogger(__name__)


class PlaywrightEngine:
    """Browser instance wrapper for SVG-to-PNG rendering."""

    def __init__(self, browser) -> None:
        self._browser = browser
        self._in_use = False

    async def render_svg_to_png(
        self,
        svg_string: str,
        width: int = 1200,
        height: int = 800,
    ) -> bytes:
        """Render an SVG string to PNG bytes using a headless browser page."""
        page = await self._browser.new_page(
            viewport={"width": width, "height": height}
        )
        try:
            html = f"""<!DOCTYPE html>
<html><head><style>
body {{ margin: 0; padding: 0; background: white; }}
svg {{ width: 100%; height: 100%; }}
</style></head>
<body>{svg_string}</body></html>"""
            await page.set_content(html, wait_until="networkidle")
            png_bytes = await page.screenshot(type="png", full_page=False)
            return png_bytes
        finally:
            await page.close()

    async def health_check(self) -> bool:
        try:
            page = await self._browser.new_page()
            await page.close()
            return True
        except Exception:
            return False

    @property
    def in_use(self) -> bool:
        return self._in_use

    @in_use.setter
    def in_use(self, value: bool) -> None:
        self._in_use = value
