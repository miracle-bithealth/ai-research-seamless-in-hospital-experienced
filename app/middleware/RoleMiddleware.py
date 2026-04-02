from fastapi import HTTPException, status, Depends
from config.setting import env

class RoleMiddleware:
    def __new__(cls, role: str, security_func: callable):
        async def dependency(payload: str = Depends(security_func)):
            roles = payload.get(env.JWT_ROLES_INDEX, '')
            if not any(r in roles.split(',') for r in role.split(',')):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, 
                    detail={"msg": "User does not have the required role"},
                    headers={"Authorization": "Bearer"},
                )
            return payload
        return dependency
