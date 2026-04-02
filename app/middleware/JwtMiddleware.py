from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Annotated
from config.setting import env
import base64

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class CredentialError(Exception):
    pass

class JwtMiddleware:
    def __init__(self, algo: str = "HS256", key: str = "JWT_HS_SECRET"):
        self.algorithms = algo
        self.key_string = key
        
        key = getattr(env, self.key_string.upper(), None)
        if not key:
            raise AttributeError(f"Invalid JWT key empty or not found in env: {self.key_string}")
        self.key = base64.b64decode(key)
        
    async def __call__(
        self, 
        token: Annotated[str, Depends(oauth2_scheme)],
        ):
        try:
            payload = jwt.decode(token, self.key, algorithms=[self.algorithms])
            if (
                payload.get("exp") is None or
                payload.get("service_name").upper() != env.APP_NAME.upper() or
                payload.get("deployment_environment").upper() != env.APP_ENV.upper()
            ):
                raise CredentialError("Could not validate credentials")
            return payload
        
        except (JWTError, CredentialError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"msg": "Could not validate credentials. Invalid token."},
                headers={"Authorization": "Bearer"},
            )

