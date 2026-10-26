import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from . import config, db, imap_client, reports

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None

_last_poll_status = {"at": None, "success": None, "error": None, "processed": 0}


def poll_mailbox() -> int:
    global _last_poll_status
    try:
        count = imap_client.poll_inbox()
        _last_poll_status = {"at": db.now_iso(), "success": True, "error": None, "processed": count}
        if count:
            logger.info("IMAP poll: processed %d new email(s)", count)
        return count
    except Exception as exc:
        _last_poll_status = {"at": db.now_iso(), "success": False, "error": str(exc), "processed": 0}
        logger.exception("IMAP poll failed")
        return 0


def last_poll_status() -> dict:
    return dict(_last_poll_status)


def weekly_report_tick() -> None:
    try:
        if reports.maybe_send_weekly():
            logger.info("Weekly report emailed")
    except Exception:
        logger.exception("Weekly report check failed")


def start_scheduler() -> Optional[BackgroundScheduler]:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()
    if config.imap_configured():
        _scheduler.add_job(
            poll_mailbox,
            "interval",
            minutes=config.IMAP_POLL_INTERVAL_MINUTES,
            id="mailbox_poll",
        )
    # Hourly, and the check itself decides whether it's time: that way the
    # owner can set a recipient or change the timezone without a restart.
    _scheduler.add_job(weekly_report_tick, "interval", hours=1, id="weekly_report")
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
