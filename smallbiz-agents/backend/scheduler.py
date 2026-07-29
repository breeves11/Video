import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from . import config, imap_client

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def poll_mailbox() -> int:
    count = imap_client.poll_inbox()
    if count:
        logger.info("IMAP poll: processed %d new email(s)", count)
    return count


def start_scheduler() -> Optional[BackgroundScheduler]:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    if not config.imap_configured():
        return None

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        poll_mailbox,
        "interval",
        minutes=config.IMAP_POLL_INTERVAL_MINUTES,
        id="mailbox_poll",
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
