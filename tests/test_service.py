import unittest

from wechat_robot.config import BotConfig
from wechat_robot.models import IncomingMessage
from wechat_robot.policy import BroadcastPolicy, DecisionReason
from wechat_robot.service import BroadcastService, HandlingOutcome


class FakeGateway:
    def __init__(self, statuses: list[int]) -> None:
        self.statuses = statuses
        self.calls: list[tuple[str, str]] = []

    def broadcast_all(self, room_id: str, text: str) -> int:
        self.calls.append((room_id, text))
        return self.statuses.pop(0)


class BroadcastServiceTests(unittest.TestCase):
    def message(self, sender_id: str = "wxid_ok") -> IncomingMessage:
        return IncomingMessage(
            message_type=1,
            sender_id=sender_id,
            room_id="room@chatroom",
            content="@Bot\u2005通知",
            from_group=True,
            from_self=False,
            mentions_bot=True,
            bot_alias="Bot",
        )

    def service(self, gateway: FakeGateway) -> BroadcastService:
        config = BotConfig(
            frozenset({"room@chatroom"}),
            frozenset({"wxid_ok"}),
            10,
            "INFO",
        )
        return BroadcastService(BroadcastPolicy(config), gateway)

    def test_sends_authorized_message(self) -> None:
        gateway = FakeGateway([0])
        result = self.service(gateway).handle(self.message(), now=100.0)
        self.assertEqual(result.outcome, HandlingOutcome.SENT)
        self.assertEqual(gateway.calls, [("room@chatroom", "通知")])

    def test_does_not_send_rejected_message(self) -> None:
        gateway = FakeGateway([0])
        result = self.service(gateway).handle(self.message("wxid_other"), now=100.0)
        self.assertEqual(result.outcome, HandlingOutcome.REJECTED)
        self.assertEqual(result.reason, DecisionReason.SENDER_NOT_ALLOWED)
        self.assertEqual(gateway.calls, [])

    def test_reports_send_failure(self) -> None:
        gateway = FakeGateway([7])
        result = self.service(gateway).handle(self.message(), now=100.0)
        self.assertEqual(result.outcome, HandlingOutcome.SEND_FAILED)
        self.assertEqual(result.send_status, 7)

    def test_failed_send_does_not_start_cooldown(self) -> None:
        gateway = FakeGateway([7, 0])
        service = self.service(gateway)
        first = service.handle(self.message(), now=100.0)
        second = service.handle(self.message(), now=101.0)
        self.assertEqual(first.outcome, HandlingOutcome.SEND_FAILED)
        self.assertEqual(second.outcome, HandlingOutcome.SENT)

    def test_successful_send_starts_cooldown(self) -> None:
        gateway = FakeGateway([0])
        service = self.service(gateway)
        first = service.handle(self.message(), now=100.0)
        second = service.handle(self.message(), now=101.0)
        self.assertEqual(first.outcome, HandlingOutcome.SENT)
        self.assertEqual(second.outcome, HandlingOutcome.REJECTED)
        self.assertEqual(second.reason, DecisionReason.COOLDOWN)


if __name__ == "__main__":
    unittest.main()
