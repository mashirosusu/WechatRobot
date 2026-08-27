import json
import unittest
from pathlib import Path
from queue import Empty
from uuid import uuid4

from wechat_robot.__main__ import main, run
from wechat_robot.models import IncomingMessage


def valid_message() -> IncomingMessage:
    return IncomingMessage(
        message_type=1,
        sender_id="wxid_ok",
        room_id="room@chatroom",
        content="@Bot\u2005通知",
        from_group=True,
        from_self=False,
        mentions_bot=True,
        bot_alias="Bot",
    )


class FakeGateway:
    bot_id = "wxid_bot"

    def __init__(
        self,
        events: list[object] | None = None,
        start_result: bool = True,
        send_error: Exception | None = None,
    ) -> None:
        self.events = list(events or [])
        self.start_result = start_result
        self.send_error = send_error
        self.started = False
        self.closed = False
        self.sent: list[tuple[str, str]] = []

    def start(self) -> bool:
        self.started = True
        return self.start_result

    def receiving(self) -> bool:
        return bool(self.events)

    def receive(self) -> IncomingMessage:
        event = self.events.pop(0)
        if isinstance(event, Exception):
            raise event
        return event

    def broadcast_all(self, room_id: str, text: str) -> int:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((room_id, text))
        return 0

    def close(self) -> None:
        self.closed = True


class MainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config_path = Path.cwd() / f".test-main-config-{uuid4().hex}.json"
        self.addCleanup(self.config_path.unlink, missing_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "allowed_rooms": ["room@chatroom"],
                    "allowed_senders": ["wxid_ok"],
                    "cooldown_seconds": 10,
                    "log_level": "INFO",
                }
            ),
            encoding="utf-8",
        )

    def test_run_starts_handles_and_closes(self) -> None:
        gateway = FakeGateway([valid_message()])
        result = run(self.config_path, lambda: gateway)
        self.assertEqual(result, 0)
        self.assertTrue(gateway.started)
        self.assertEqual(gateway.sent, [("room@chatroom", "通知")])
        self.assertTrue(gateway.closed)

    def test_start_failure_still_closes(self) -> None:
        gateway = FakeGateway(start_result=False)
        with self.assertRaisesRegex(RuntimeError, "enable message reception"):
            run(self.config_path, lambda: gateway)
        self.assertTrue(gateway.closed)

    def test_empty_queue_is_ignored(self) -> None:
        gateway = FakeGateway([Empty(), valid_message()])
        result = run(self.config_path, lambda: gateway)
        self.assertEqual(result, 0)
        self.assertEqual(gateway.sent, [("room@chatroom", "通知")])

    def test_processing_exception_is_logged(self) -> None:
        gateway = FakeGateway([valid_message()], send_error=RuntimeError("send broke"))
        with self.assertLogs("wechat_robot", level="ERROR") as captured:
            result = run(self.config_path, lambda: gateway)
        self.assertEqual(result, 0)
        self.assertTrue(any("Failed to process" in line for line in captured.output))
        self.assertTrue(gateway.closed)

    def test_main_returns_zero_on_success(self) -> None:
        gateway = FakeGateway([])
        result = main(["--config", str(self.config_path)], lambda: gateway)
        self.assertEqual(result, 0)

    def test_main_returns_one_for_runtime_error(self) -> None:
        def failing_factory() -> FakeGateway:
            raise RuntimeError("cannot start")

        result = main(["--config", str(self.config_path)], failing_factory)
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
