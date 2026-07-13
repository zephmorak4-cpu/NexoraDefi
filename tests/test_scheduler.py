from app.core.config import Settings
from app.jobs.scheduler import build_scheduler


def test_scheduler_registers_no_automatic_workflows_after_reset():
    settings = Settings()
    scheduler = build_scheduler(settings)

    assert scheduler.get_jobs() == []
