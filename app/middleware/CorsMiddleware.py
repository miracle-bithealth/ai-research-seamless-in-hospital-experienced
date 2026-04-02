
import re
from typing import Annotated
from config.setting import env
from fastapi import Header, HTTPException, status
from typing_extensions import Annotated

_LOCAL_ORIGIN_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")

class CorsMiddleware:
    async def __call__(self, origin: Annotated[str, Header()] = None):
        try:
            allowed = env.ALLOWED_ORIGINS.split(",")
            is_allowed = origin in allowed
            if not is_allowed and env.APP_ENV == "local" and origin:
                is_allowed = bool(_LOCAL_ORIGIN_RE.match(origin))
            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail= {
                        "msg": "Not allowed by cors",
                        "data": None,
                        "error": None
                    }
                )
            return True
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail= {
                        "msg": "Not allowed by cors",
                        "data": None,
                        "error": e
                    },
                    headers={"Authorization": "Bearer"},
                )

