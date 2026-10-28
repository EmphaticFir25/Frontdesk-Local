"""Availability logic. Kept separate so a real calendar integration can replace the store lookup."""
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

from .config import WEEKDAYS, BusinessConfig
from .store import Store


def day_window(cfg: BusinessConfig, day: date) -> tuple[datetime, datetime] | None:
    """Return the open and close datetimes for a date, or None if closed."""
    window = cfg.hours.get(WEEKDAYS[day.weekday()])
    if not window:
        return None
    tz = ZoneInfo(cfg.timezone)
    start_s, end_s = window.split("-")
    open_at = datetime.combine(day, dtime.fromisoformat(start_s.strip()), tzinfo=tz)
    close_at = datetime.combine(day, dtime.fromisoformat(end_s.strip()), tzinfo=tz)
    return open_at, close_at


def open_slots(cfg: BusinessConfig, store: Store, day: date, minutes: int) -> list[datetime]:
    """Start times on `day` that fit a `minutes`-long service without overlapping bookings."""
    window = day_window(cfg, day)
    if window is None:
        return []
    open_at, close_at = window
    now = datetime.now(ZoneInfo(cfg.timezone))
    booked = store.booked_intervals(cfg.id, day.isoformat())

    slots = []
    t = open_at
    length = timedelta(minutes=minutes)
    while t + length <= close_at:
        end = t + length
        overlaps = any(s < end and t < e for s, e in booked)
        if not overlaps and t > now:
            slots.append(t)
        t += timedelta(minutes=cfg.slot_minutes)
    return slots


def is_open_slot(cfg: BusinessConfig, store: Store, start: datetime, minutes: int) -> bool:
    """Re-check one specific start time right before booking, since slots can be taken mid-call."""
    return any(start == s for s in open_slots(cfg, store, start.date(), minutes))
