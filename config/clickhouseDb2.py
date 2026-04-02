from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config.setting import env
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

metadata = MetaData()
Base = declarative_base(metadata=metadata)

CLICKHOUSE_URL = (
    f"clickhouse+asynch://{env.CLICKHOUSE_USER}:{env.CLICKHOUSE_PASSWORD}@"
    f"{env.CLICKHOUSE_HOST}:{env.CLICKHOUSE_PORT}/{env.CLICKHOUSE_DB}"
)

engine = create_async_engine(
    CLICKHOUSE_URL,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
