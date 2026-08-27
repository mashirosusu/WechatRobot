import json
import unittest
from pathlib import Path
from uuid import uuid4

from wechat_robot.config import ConfigurationError, load_config


class LoadConfigTests(unittest.TestCase):
    def write_config(self, payload: object) -> Path:
        path = Path.cwd() / f".test-config-{uuid4().hex}.json"
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_loads_valid_configuration(self) -> None:
        config = load_config(self.write_config({
            "allowed_rooms": ["123@chatroom"],
            "allowed_senders": ["wxid_authorized"],
            "cooldown_seconds": 10,
            "log_level": "INFO",
        }))

        self.assertEqual(config.allowed_rooms, frozenset({"123@chatroom"}))
        self.assertEqual(config.allowed_senders, frozenset({"wxid_authorized"}))
        self.assertEqual(config.cooldown_seconds, 10)
        self.assertEqual(config.log_level, "INFO")

    def test_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "not found"):
            load_config(Path("missing-config.json"))

    def test_rejects_unknown_fields(self) -> None:
        path = self.write_config({
            "allowed_rooms": ["123@chatroom"],
            "allowed_senders": ["wxid_authorized"],
            "cooldown_seconds": 10,
            "log_level": "INFO",
            "secret_mode": True,
        })
        with self.assertRaisesRegex(ConfigurationError, "Unknown configuration fields"):
            load_config(path)

    def test_rejects_empty_or_invalid_allowlists(self) -> None:
        invalid_payloads = [
            {"allowed_rooms": [], "allowed_senders": ["wxid_a"]},
            {"allowed_rooms": ["not-a-room"], "allowed_senders": ["wxid_a"]},
            {"allowed_rooms": ["1@chatroom"], "allowed_senders": []},
            {"allowed_rooms": ["1@chatroom"], "allowed_senders": [""]},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ConfigurationError):
                load_config(self.write_config(payload))

    def test_rejects_invalid_cooldown(self) -> None:
        for value in (-1, 3601, 1.5, True):
            payload = {
                "allowed_rooms": ["1@chatroom"],
                "allowed_senders": ["wxid_a"],
                "cooldown_seconds": value,
            }
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                load_config(self.write_config(payload))

    def test_rejects_invalid_log_level(self) -> None:
        path = self.write_config({
            "allowed_rooms": ["1@chatroom"],
            "allowed_senders": ["wxid_a"],
            "log_level": "VERBOSE",
        })
        with self.assertRaisesRegex(ConfigurationError, "log_level"):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
