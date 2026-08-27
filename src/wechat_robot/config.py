from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BotConfig:
    allowed_rooms: frozenset[str]
    allowed_senders: frozenset[str]
    cooldown_seconds: int = 10
    log_level: str = "INFO"


def load_config(path: Path) -> BotConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Configuration file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot read configuration: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigurationError("Configuration root must be a JSON object")

    allowed_keys = {"allowed_rooms", "allowed_senders", "cooldown_seconds", "log_level"}
    unknown = set(data) - allowed_keys
    if unknown:
        raise ConfigurationError(f"Unknown configuration fields: {', '.join(sorted(unknown))}")

    rooms = _nonempty_strings(data.get("allowed_rooms"), "allowed_rooms")
    if any(not room.endswith("@chatroom") for room in rooms):
        raise ConfigurationError("Every allowed_rooms value must end with @chatroom")

    senders = _nonempty_strings(data.get("allowed_senders"), "allowed_senders")
    cooldown = data.get("cooldown_seconds", 10)
    if isinstance(cooldown, bool) or not isinstance(cooldown, int) or not 0 <= cooldown <= 3600:
        raise ConfigurationError("cooldown_seconds must be an integer from 0 through 3600")

    log_level = data.get("log_level", "INFO")
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level not in valid_levels:
        raise ConfigurationError(f"log_level must be one of {', '.join(sorted(valid_levels))}")

    return BotConfig(frozenset(rooms), frozenset(senders), cooldown, log_level)


def _nonempty_strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{field} must be a non-empty JSON array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigurationError(f"{field} must contain only non-empty strings")
    return [item.strip() for item in value]
