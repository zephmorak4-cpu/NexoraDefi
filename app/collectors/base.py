from sqlalchemy.ext.asyncio import AsyncSession

from app.services.http import AsyncAPIClient
from app.services.repository import DataRepository


class BaseCollector:
    def __init__(self, session: AsyncSession, client: AsyncAPIClient) -> None:
        self.session = session
        self.client = client
        self.repository = DataRepository(session)

    async def close(self) -> None:
        await self.client.close()

