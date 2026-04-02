from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.declarative import declarative_base
from .setting import env
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# --- Required for Alembic autogenerate support (metadata, Base and SYNC_DB_URL) --- 
metadata = MetaData()
Base = declarative_base(metadata=metadata)
SYNC_DB_URL = (
    f"postgresql+psycopg2://{env.DB_USER}:{env.DB_PASSWORD}@"
    f"{env.DB_HOST}:{env.DB_PORT}/{env.DB_NAME}"
)

ASYNC_DB_URL = (
    f"postgresql+asyncpg://{env.DB_USER}:{env.DB_PASSWORD}@"
    f"{env.DB_HOST}:{env.DB_PORT}/{env.DB_NAME}"
)

sync_engine = create_engine(SYNC_DB_URL, echo=False)
async_engine = create_async_engine(ASYNC_DB_URL, echo=False)

async_session = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
async def get_db():
    async with async_session() as session:
        yield session
