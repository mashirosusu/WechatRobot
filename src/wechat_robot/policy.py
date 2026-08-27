from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import Enum

from .config import BotConfig
from .models import IncomingMessage


class DecisionReason(str, Enum):
    ALLOWED = "allowed"
    NOT_GROUP = "not_group"
    NOT_TEXT = "not_text"
    FROM_SELF = "from_self"
    NOT_MENTIONED = "not_mentioned"
    ROOM_NOT_ALLOWED = "room_not_allowed"
    SENDER_NOT_ALLOWED = "sender_not_allowed"
    INVALID_MENTION_FORMAT = "invalid_mention_format"
    EMPTY_TEXT = "empty_text"
    COOLDOWN = "cooldown"


@dataclass(frozen=True, slots=True)
class BroadcastDecision:
    allowed: bool
    reason: DecisionReason
    text: str = ""


class BroadcastPolicy:
    def __init__(self, config: BotConfig) -> None:
        self._config = config
        self._last_success: dict[tuple[str, str], float] = {}

    def evaluate(self, message: IncomingMessage, now: float | None = None) -> BroadcastDecision:
        checks = (
            (not message.from_group, DecisionReason.NOT_GROUP),
            (message.message_type != 1, DecisionReason.NOT_TEXT),
            (message.from_self, DecisionReason.FROM_SELF),
            (not message.mentions_bot, DecisionReason.NOT_MENTIONED),
            (message.room_id not in self._config.allowed_rooms, DecisionReason.ROOM_NOT_ALLOWED),
            (message.sender_id not in self._config.allowed_senders, DecisionReason.SENDER_NOT_ALLOWED),
        )
        for rejected, reason in checks:
            if rejected:
                return BroadcastDecision(False, reason)

        if not message.bot_alias:
            return BroadcastDecision(False, DecisionReason.INVALID_MENTION_FORMAT)
        pattern = rf"^\s*@{re.escape(message.bot_alias)}(?:(?:\u2005|\s)+|$)"
        match = re.match(pattern, message.content)
        if not match:
            return BroadcastDecision(False, DecisionReason.INVALID_MENTION_FORMAT)
        text = message.content[match.end():].strip()
        if not text:
            return BroadcastDecision(False, DecisionReason.EMPTY_TEXT)

        current = time.monotonic() if now is None else now
        last = self._last_success.get((message.room_id, message.sender_id))
        if last is not None and current - last < self._config.cooldown_seconds:
            return BroadcastDecision(False, DecisionReason.COOLDOWN)
        return BroadcastDecision(True, DecisionReason.ALLOWED, text)

    def record_success(self, message: IncomingMessage, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        self._last_success[(message.room_id, message.sender_id)] = current
