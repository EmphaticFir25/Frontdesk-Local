"""Tools the LLM can call during a call. Schemas use the OpenAI function-calling format,
which LM Studio, Ollama, and most cloud providers accept."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .config import BusinessConfig
from .scheduling import is_open_slot, open_slots
from .store import Store


@dataclass
class ToolContext:
    cfg: BusinessConfig
    store: Store
    caller_phone: str


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Find open appointment times on a given date for a service. "
                           "Call this before offering any time to the caller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date as YYYY-MM-DD"},
                    "service": {"type": "string", "description": "Exact service name from the business info"},
                },
                "required": ["date", "service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a confirmed appointment. Only call after the caller has agreed to a "
                           "specific time and you have their name and phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "start": {"type": "string", "description": "ISO 8601 start time returned by check_availability"},
                    "caller_name": {"type": "string"},
                    "caller_phone": {"type": "string"},
                },
                "required": ["service", "start", "caller_name", "caller_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_message",
            "description": "Save a message for the staff to return. Use when you cannot answer, "
                           "the caller asks for something you cannot book, or the caller wants a callback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {"type": "string"},
                    "caller_phone": {"type": "string"},
                    "message": {"type": "string", "description": "What the caller needs, in one or two sentences"},
                },
                "required": ["caller_name", "caller_phone", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "Transfer the call to a staff member. Use for urgent issues, complaints, "
                           "or anything the escalation rules say to hand off.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    },
]


def _fmt_time(dt: datetime) -> str:
    return dt.strftime("%A %B %d at %I:%M %p").replace(" 0", " ")


def check_availability(ctx: ToolContext, date_str: str, service: str) -> dict:
    svc = ctx.cfg.service(service)
    if svc is None:
        return {"ok": False, "error": f"Unknown service. Options: {[s.name for s in ctx.cfg.services]}"}
    try:
        day = date.fromisoformat(date_str)
    except ValueError:
        return {"ok": False, "error": "Date must be YYYY-MM-DD"}

    slots = open_slots(ctx.cfg, ctx.store, day, svc.minutes)[:6]
    if not slots:
        return {"ok": True, "date": date_str, "open_times": [],
                "note": "No openings that day. Offer another day or take a message."}
    return {
        "ok": True,
        "date": date_str,
        "open_times": [{"label": _fmt_time(s), "start": s.isoformat()} for s in slots],
    }


def book_appointment(ctx: ToolContext, service: str, start: str,
                     caller_name: str, caller_phone: str) -> dict:
    svc = ctx.cfg.service(service)
    if svc is None:
        return {"ok": False, "error": "Unknown service"}
    try:
        starts = datetime.fromisoformat(start)
    except ValueError:
        return {"ok": False, "error": "Invalid start time"}
    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=ZoneInfo(ctx.cfg.timezone))

    if not is_open_slot(ctx.cfg, ctx.store, starts, svc.minutes):
        return {"ok": False,
                "error": "That time is no longer available. Check availability again."}

    ends = starts + timedelta(minutes=svc.minutes)
    appt_id = ctx.store.add_appointment(
        ctx.cfg.id, caller_name, caller_phone or ctx.caller_phone, svc.name, starts, ends
    )
    return {"ok": True, "confirmation_id": appt_id, "service": svc.name,
            "when": _fmt_time(starts), "name": caller_name}


def take_message(ctx: ToolContext, caller_name: str, caller_phone: str, message: str) -> dict:
    msg_id = ctx.store.add_message(ctx.cfg.id, caller_name, caller_phone or ctx.caller_phone, message)
    return {"ok": True, "message_id": msg_id,
            "note": "Message saved. Tell the caller someone will call them back."}


def transfer_to_human(ctx: ToolContext, reason: str) -> dict:
    if not ctx.cfg.transfer_number:
        return {"ok": False,
                "note": "No staff line is set up. Take a message and tell the caller it's urgent."}
    return {"ok": True, "action": "transfer", "number": ctx.cfg.transfer_number, "reason": reason}


HANDLERS = {
    "check_availability": lambda ctx, a: check_availability(ctx, a["date"], a["service"]),
    "book_appointment": lambda ctx, a: book_appointment(
        ctx, a["service"], a["start"], a["caller_name"], a.get("caller_phone", "")),
    "take_message": lambda ctx, a: take_message(
        ctx, a["caller_name"], a.get("caller_phone", ""), a["message"]),
    "transfer_to_human": lambda ctx, a: transfer_to_human(ctx, a["reason"]),
}


def dispatch(name: str, args: dict, ctx: ToolContext) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"Unknown tool {name}"}
    try:
        return handler(ctx, args)
    except (KeyError, TypeError) as exc:
        return {"ok": False, "error": f"Bad arguments: {exc}"}
