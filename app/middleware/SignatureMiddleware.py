from typing_extensions import Annotated
from fastapi import Header, Request, HTTPException, status
from config.setting import env
from app.utils.SignatureUtils import verify_signature
from datetime import datetime, timezone

class SignatureMiddleware:
    async def __call__(
        self, 
        request: Request, 
        x_signature: Annotated[str, Header()], 
        x_timestamp: Annotated[str, Header()]
    ):
        try:
            if abs(int(datetime.now(timezone.utc).timestamp()) - int(x_timestamp)) > env.SIGNATURE_TIMEOUT:
                raise ValueError("Timestamp is too old or invalid")

            body = await request.body()
            if not verify_signature(body, x_timestamp, x_signature):
                raise ValueError("Invalid signature")
            
            return body

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "msg": "Could not validate signature",
                    "data": None,
                    "error": e
                },
                headers={"Authorization": "Bearer"},
            )
