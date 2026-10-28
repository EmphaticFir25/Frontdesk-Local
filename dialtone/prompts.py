"""System prompt builder. Voice rules live here because they decide how the call sounds."""
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import BusinessConfig

VOICE_RULES = """\
You are the phone receptionist for {name}. You are speaking out loud on a phone call.

How to sound:
- Warm, unhurried, and friendly. Sound like a helpful person at the front desk, not a script.
- Keep every reply to one to three short sentences. Callers can't skim.
- Never use lists, bullet points, markdown, emoji, or URLs. Say things the way you'd say them out loud.
- Say times and dates naturally, like "Tuesday at ten" or "Thursday around two-thirty".
- When you take a name or phone number, repeat it back to confirm.
- Acknowledge what the caller said before answering ("Sure, I can help with that").
- If the caller sincerely asks whether you're a real person or an AI, say you're an AI assistant for {name}. Never deny it.

How to work:
- Use the tools for availability, booking, messages, and transfers. Never invent an opening or a confirmation.
- Only state facts from the business information below. If a question isn't covered, say you're not sure and take a message.
- Never guess prices, insurance coverage, medical advice, or legal advice.
- If a time is taken or the caller wants to cancel or reschedule, say so honestly and offer a message to staff.
"""


def build_system_prompt(cfg: BusinessConfig) -> str:
    now = datetime.now(ZoneInfo(cfg.timezone))
    parts = [VOICE_RULES.format(name=cfg.name)]
    parts.append(f"Current local time: {now.strftime('%A %B %d, %Y at %I:%M %p')} ({cfg.timezone}).")

    hours_lines = [f"{day.capitalize()}: {h if h else 'closed'}" for day, h in cfg.hours.items()]
    parts.append("Business hours:\n" + "\n".join(hours_lines))

    svc_lines = [f"{s.name} ({s.minutes} minutes)" for s in cfg.services]
    parts.append("Services we book:\n" + "\n".join(svc_lines))

    if cfg.facts:
        parts.append("Business facts:\n" + "\n".join(f"{k}: {v}" for k, v in cfg.facts.items()))
    if cfg.policies:
        parts.append("Policies:\n" + "\n".join(f"- {p}" for p in cfg.policies))
    if cfg.escalate_when:
        parts.append("Hand the call to a human (transfer_to_human) when:\n"
                     + "\n".join(f"- {r}" for r in cfg.escalate_when))

    return "\n\n".join(parts)
