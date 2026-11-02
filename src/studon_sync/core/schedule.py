"""When is the next automatic sync due? (The app's own timer asks this every minute.)"""

from datetime import datetime, timedelta
from typing import Optional

from .settings import Settings


def is_due(settings: Settings, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    sched = settings.schedule
    last = datetime.fromisoformat(settings.last_sync) if settings.last_sync else None

    if sched.mode == "interval":
        return last is None or now - last >= timedelta(hours=max(1, sched.hours))

    if sched.mode == "daily":
        hour, minute = (int(x) for x in sched.time.split(":"))
        today_slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Catches up if the computer was asleep/off at the scheduled time.
        return now >= today_slot and (last is None or last < today_slot)

    return False
