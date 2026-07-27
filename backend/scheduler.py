import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from . import config
from .niche_finder import discover_niches
from .niches_repo import save_niches

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def poll_niches() -> int:
    """Re-run niche discovery and persist fresh scores. Returns count saved."""
    niches = discover_niches()
    save_niches(niches)
    logger.info("Niche poll complete: %d niches scored", len(niches))
    return len(niches)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        poll_niches,
        "interval",
        hours=config.POLL_INTERVAL_HOURS,
        id="niche_poll",
        next_run_time=None,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
