from sqlalchemy.ext.asyncio import create_async_engine

from app.database.health import check_database


async def test_database_connection():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    assert await check_database(engine) is True
    await engine.dispose()

