from unittest.mock import AsyncMock, patch

from app.jobs import tasks


async def test_scheduler_job_delegates_to_collector():
    with patch.object(tasks, "run_collector", new=AsyncMock(return_value=2)) as run:
        assert await tasks.refresh_market() == 2
        run.assert_awaited_once_with(tasks.MarketCollector)

