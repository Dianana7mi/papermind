from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

settings().storage_path.mkdir(parents=True, exist_ok=True)
engine = create_async_engine(settings().database_url, poolclass=NullPool, hide_parameters=True)
if settings().database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


Session = async_sessionmaker(engine, expire_on_commit=False)


async def session():
    async with Session() as db:
        yield db
