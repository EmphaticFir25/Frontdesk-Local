"""Per-business configuration. One YAML file per client."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@dataclass
class Service:
    name: str
    minutes: int


@dataclass
class BusinessConfig:
    id: str
    name: str
    timezone: str
    hours: dict                      # weekday -> "09:00-17:00" or None (closed)
    services: list[Service]
    facts: dict = field(default_factory=dict)      # address, phone, parking, insurance...
    policies: list[str] = field(default_factory=list)
    escalate_when: list[str] = field(default_factory=list)  # plain-English rules
    transfer_number: str | None = None
    slot_minutes: int = 30

    def service(self, name: str) -> Service | None:
        for s in self.services:
            if s.name.lower() == name.lower():
                return s
        return None


def load_business(path: str | Path) -> BusinessConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return BusinessConfig(
        id=raw["id"],
        name=raw["name"],
        timezone=raw["timezone"],
        hours={day: raw["hours"].get(day) for day in WEEKDAYS},
        services=[Service(**s) for s in raw["services"]],
        facts=raw.get("facts", {}),
        policies=raw.get("policies", []),
        escalate_when=raw.get("escalate_when", []),
        transfer_number=raw.get("transfer_number"),
        slot_minutes=raw.get("slot_minutes", 30),
    )
