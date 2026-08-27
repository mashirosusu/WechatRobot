import unittest

from wechat_robot.config import BotConfig
from wechat_robot.models import IncomingMessage
from wechat_robot.policy import BroadcastPolicy, DecisionReason


class BroadcastPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        config = BotConfig(
            frozenset({"room@chatroom"}),
            frozenset({"wxid_ok"}),
            10,
            "INFO",
        )
        self.policy = BroadcastPolicy(config)

    def message(self, **overrides: object) -> IncomingMessage:
        values = {
            "message_type": 1,
            "sender_id": "wxid_ok",
            "room_id": "room@chatroom",
            "content": "@Bot\u2005通知",
            "from_group": True,
            "from_self": False,
            "mentions_bot": True,
            "bot_alias": "Bot",
        }
        values.update(overrides)
        return IncomingMessage(**values)

    def test_allows_valid_message_and_extracts_text(self) -> None:
        decision = self.policy.evaluate(self.message(), now=100.0)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, DecisionReason.ALLOWED)
        self.assertEqual(decision.text, "通知")

    def test_rejects_non_group_message(self) -> None:
        decision = self.policy.evaluate(self.message(from_group=False), now=100.0)
        self.assertEqual(decision.reason, DecisionReason.NOT_GROUP)

    def test_rejects_non_text_message(self) -> None:
        decision = self.policy.evaluate(self.message(message_type=3), now=100.0)
        self.assertEqual(decision.reason, DecisionReason.NOT_TEXT)

    def test_rejects_self_message(self) -> None:
        decision = self.policy.evaluate(self.message(from_self=True), now=100.0)
        self.assertEqual(decision.reason, DecisionReason.FROM_SELF)

    def test_rejects_message_without_actual_mention(self) -> None:
        decision = self.policy.evaluate(self.message(mentions_bot=False), now=100.0)
        self.assertEqual(decision.reason, DecisionReason.NOT_MENTIONED)

    def test_rejects_room_outside_allowlist(self) -> None:
        decision = self.policy.evaluate(self.message(room_id="other@chatroom"), now=100.0)
        self.assertEqual(decision.reason, DecisionReason.ROOM_NOT_ALLOWED)

    def test_rejects_sender_outside_allowlist(self) -> None:
        decision = self.policy.evaluate(self.message(sender_id="wxid_other"), now=100.0)
        self.assertEqual(decision.reason, DecisionReason.SENDER_NOT_ALLOWED)

    def test_rejects_invalid_leading_mention_format(self) -> None:
        decision = self.policy.evaluate(self.message(content="通知 @Bot"), now=100.0)
        self.assertEqual(decision.reason, DecisionReason.INVALID_MENTION_FORMAT)

    def test_rejects_empty_remaining_text(self) -> None:
        decision = self.policy.evaluate(self.message(content="@Bot\u2005  "), now=100.0)
        self.assertEqual(decision.reason, DecisionReason.EMPTY_TEXT)

    def test_removes_group_alias_containing_spaces(self) -> None:
        decision = self.policy.evaluate(
            self.message(content="@Relay Bot\u2005重要通知", bot_alias="Relay Bot"),
            now=100.0,
        )
        self.assertEqual(decision.text, "重要通知")

    def test_rejects_during_cooldown_and_allows_at_expiry(self) -> None:
        message = self.message()
        self.policy.record_success(message, now=100.0)

        blocked = self.policy.evaluate(message, now=109.999)
        allowed = self.policy.evaluate(message, now=110.0)

        self.assertEqual(blocked.reason, DecisionReason.COOLDOWN)
        self.assertTrue(allowed.allowed)


if __name__ == "__main__":
    unittest.main()
