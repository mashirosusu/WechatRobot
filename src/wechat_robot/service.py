from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .models import IncomingMessage
from .policy import BroadcastPolicy, DecisionReason


class BroadcastGateway(Protocol):
    def broadcast_all(self, room_id: str, text: str) -> int: ...


class HandlingOutcome(str, Enum):
    REJECTED = "rejected"
    SENT = "sent"
    SEND_FAILED = "send_failed"


@dataclass(frozen=True, slots=True)
class HandlingResult:
    outcome: HandlingOutcome
    reason: DecisionReason
    send_status: int | None = None


class BroadcastService:
    def __init__(self, policy: BroadcastPolicy, gateway: BroadcastGateway) -> None:
        self._policy = policy
        self._gateway = gateway

    def handle(self, message: IncomingMessage, now: float | None = None) -> HandlingResult:
        decision = self._policy.evaluate(message, now)
        if not decision.allowed:
            return HandlingResult(HandlingOutcome.REJECTED, decision.reason)

        status = self._gateway.broadcast_all(message.room_id, decision.text)
        if status != 0:
            return HandlingResult(HandlingOutcome.SEND_FAILED, decision.reason, status)

        self._policy.record_success(message, now)
        return HandlingResult(HandlingOutcome.SENT, decision.reason, status)
