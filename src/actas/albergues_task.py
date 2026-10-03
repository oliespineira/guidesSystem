import asyncio
import os

from src.actas.albergues import send_reminders
from src.db import get_connection
from src.messaging.notifier import Notifier


def _check_once(notifier: Notifier) -> int:
    conn = get_connection()
    try:
        return send_reminders(conn, notifier)
    finally:
        conn.close()


async def booking_reminder_loop(notifier: Notifier) -> None:
    """In-process background task (§1b): no cron container, no Celery. Runs inside the
    same event loop as the app, checks deadlines, then sleeps until the next check."""
    interval = int(os.environ.get("BOOKING_CHECK_SECONDS", "3600"))
    while True:
        # SQLite calls block, so run them in a worker thread instead of freezing the event loop.
        await asyncio.to_thread(_check_once, notifier)
        await asyncio.sleep(interval)