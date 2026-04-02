from math import ceil
from fastapi import HTTPException, Request, Response
from fastapi import status
import redis.asyncio as redis
from config.setting import env
from redis.asyncio.retry import Retry
from redis.backoff import ConstantBackoff
from redis.exceptions import ConnectionError, TimeoutError

redis_connection = redis.Redis(
    host=env.REDIS_RATELIMIT_HOST, 
    port=env.REDIS_RATELIMIT_PORT,
    password=env.CACHE_PASSWORD,
    username=env.CACHE_USERNAME,
    db=env.REDIS_RATELIMIT_DB, 
    encoding="utf-8", 
    decode_responses=True,
    # retry_on_error=[ConnectionError, TimeoutError],
    # retry=Retry(ConstantBackoff(backoff=1.0), 0)
)

async def service_name_identifier(request: Request):
    return request.client.host

async def custom_callback(request: Request, response: Response, pexpire: int):
    """
    default callback when too many requests
    :param request:
    :param pexpire: The remaining milliseconds
    :param response:
    :return:
    """
    expire = ceil(pexpire / 1000)

    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        {
            "msg": "Too many requests",
            "data": None
        },
        headers={"Retry-After": str(expire)},
    )
