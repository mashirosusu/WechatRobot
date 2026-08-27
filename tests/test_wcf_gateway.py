import unittest

from wechat_robot.wcf_gateway import WcfGateway


class FakeRawMessage:
    type = 1
    sender = "wxid_ok"
    roomid = "room@chatroom"
    content = "@Relay Bot\u2005通知"

    def from_group(self) -> bool:
        return True

    def from_self(self) -> bool:
        return False

    def is_at(self, wxid: str) -> bool:
        return wxid == "wxid_bot"


class FakeClient:
    def __init__(self, bot_id: str = "wxid_bot") -> None:
        self.bot_id = bot_id
        self.sent: list[tuple[str, str, str]] = []
        self.alias_calls: list[tuple[str, str]] = []
        self.cleaned = False

    def get_self_wxid(self) -> str:
        return self.bot_id

    def enable_receiving_msg(self) -> bool:
        return True

    def is_receiving_msg(self) -> bool:
        return True

    def get_msg(self) -> FakeRawMessage:
        return FakeRawMessage()

    def get_alias_in_chatroom(self, wxid: str, room_id: str) -> str:
        self.alias_calls.append((wxid, room_id))
        return "Relay Bot"

    def send_text(self, text: str, room_id: str, aters: str) -> int:
        self.sent.append((text, room_id, aters))
        return 0

    def cleanup(self) -> None:
        self.cleaned = True


class WcfGatewayTests(unittest.TestCase):
    def test_rejects_missing_logged_in_account(self) -> None:
        client = FakeClient(bot_id="")
        with self.assertRaisesRegex(RuntimeError, "wxid"):
            WcfGateway(client)
        self.assertTrue(client.cleaned)

    def test_delegates_lifecycle(self) -> None:
        client = FakeClient()
        gateway = WcfGateway(client)
        self.assertTrue(gateway.start())
        self.assertTrue(gateway.receiving())
        gateway.close()
        self.assertTrue(client.cleaned)

    def test_maps_group_message_and_alias(self) -> None:
        client = FakeClient()
        message = WcfGateway(client).receive()
        self.assertEqual(message.message_type, 1)
        self.assertEqual(message.sender_id, "wxid_ok")
        self.assertEqual(message.room_id, "room@chatroom")
        self.assertEqual(message.content, "@Relay Bot\u2005通知")
        self.assertTrue(message.from_group)
        self.assertFalse(message.from_self)
        self.assertTrue(message.mentions_bot)
        self.assertEqual(message.bot_alias, "Relay Bot")
        self.assertEqual(client.alias_calls, [("wxid_bot", "room@chatroom")])

    def test_sends_native_all_members_mention(self) -> None:
        client = FakeClient()
        status = WcfGateway(client).broadcast_all("room@chatroom", "通知")
        self.assertEqual(status, 0)
        self.assertEqual(
            client.sent,
            [("@所有人\n通知", "room@chatroom", "notify@all")],
        )


if __name__ == "__main__":
    unittest.main()
