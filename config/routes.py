# import os
# import importlib
from config.setting import env
from routes.ws import v1 as ws_v1
from routes.api import v1 as api_v1, v2 as api_v2
from routes.mcp import mcp as mcp_server
from app.middleware import CorsMiddleware
from app.middleware import JwtMiddleware
from fastapi_limiter.depends import RateLimiter
from fastapi import Depends, Security

def setup_routes(app):
    root = [
        Depends(RateLimiter(times=60, seconds=60)),
        Security(CorsMiddleware()),
        Security(JwtMiddleware()),
    ]
    app.include_router(
        api_v1.router,
        prefix="/api/v1",
        tags=["api_v1"],
        dependencies = root
    )
    app.include_router(
        api_v2.router,
        prefix="/api/v2",
        tags=["api_v2"],
        dependencies = root
    )
    app.include_router(
        ws_v1.router,
        prefix="/ws/v1",
        tags=["ws_v1"]
    )

    @app.get("/health-check", dependencies=[Depends(RateLimiter(times=60, seconds=60))])
    async def read_health():
        return {"status": "OK"}

    @app.get("/", dependencies=[Depends(RateLimiter(times=60, seconds=60))])
    async def read_root():
        return {
            "app_env": env.APP_ENV,
            "app_name": env.APP_NAME,
            "app_version": env.APP_VERSION,
        }

    app.mount("/tools", mcp_server.streamable_http_app())
