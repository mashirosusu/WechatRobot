# WeChat Group Broadcast Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish a Python 3.10 Windows bot that turns an authorized `@机器人` group message into one native `@所有人` message in the same authorized group.

**Architecture:** Keep authorization, text extraction, cooldown, and orchestration independent from WeChatFerry. A thin gateway converts WeChatFerry messages to internal values and performs the `notify@all` call; a small runner owns lifecycle and logging.

**Tech Stack:** Python 3.10, standard-library `unittest`, WeChatFerry 39.5.2.0, PC WeChat 3.9.12.51, GitHub Actions on Windows.

---

## File Structure

- `src/wechat_robot/config.py`: parse and validate local JSON configuration.
- `src/wechat_robot/models.py`: framework-independent incoming-message model.
- `src/wechat_robot/policy.py`: allowlists, mention extraction, and cooldown decisions.
- `src/wechat_robot/service.py`: coordinate policy and outbound send results.
- `src/wechat_robot/wcf_gateway.py`: adapt WeChatFerry to the internal interfaces.
- `src/wechat_robot/__main__.py`: CLI, receive loop, logging, and cleanup.
- `tests/`: standard-library unit tests for each behavior.
- `config.example.json`: sanitized runtime configuration example.
- `pyproject.toml`: package metadata, console entry point, and optional runtime dependency.
- `README.md`: Windows installation, risk warning, configuration, and acceptance test.
- `.github/workflows/tests.yml`: Python 3.10 unit tests without WeChat login.

### Task 1: Create and Link the Public GitHub Repository

**Files:** None.

- [ ] **Step 1: Confirm the desired repository does not already exist**

Run:

```powershell
gh repo view mashirosusu/WechatRobot
```

Expected: exit code is nonzero with “Could not resolve to a Repository”. If it exists, inspect it and stop rather than overwriting it.

- [ ] **Step 2: Create the public repository, set `origin`, and push the approved design and plan**

Run:

```powershell
gh repo create mashirosusu/WechatRobot --public --source . --remote origin --push --description "A guarded WeChat group @all relay bot built on WeChatFerry"
```

Expected: repository URL is printed and `main` is pushed.

- [ ] **Step 3: Verify local and remote linkage**

Run:

```powershell
git remote -v
gh repo view mashirosusu/WechatRobot --json nameWithOwner,visibility,url,defaultBranchRef
```

Expected: `origin` points at `mashirosusu/WechatRobot`, visibility is `PUBLIC`, and the default branch is `main`.

### Task 2: Add Configuration Loading With TDD

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Create: `src/wechat_robot/__init__.py`
- Create: `src/wechat_robot/config.py`

- [ ] **Step 1: Write the failing configuration tests**

Create `tests/test_config.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from wechat_robot.config import ConfigurationError, load_config


class LoadConfigTests(unittest.TestCase):
    def write_config(self, payload: object) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "config.json"
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
$env:PYTHONPATH = "src"
python -m unittest tests.test_config -v
```

Expected: import failure because `wechat_robot.config` does not exist.

- [ ] **Step 3: Implement the minimal configuration module**

Create empty `tests/__init__.py` and `src/wechat_robot/__init__.py`. Create `src/wechat_robot/config.py`:

```python
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
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run the command from Step 2. Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wechat_robot tests
git commit -m "feat: validate bot configuration"
```

### Task 3: Add Authorization, Mention Extraction, and Cooldown With TDD

**Files:**
- Create: `src/wechat_robot/models.py`
- Create: `src/wechat_robot/policy.py`
- Create: `tests/test_policy.py`

- [ ] **Step 1: Write failing policy tests**

Create `tests/test_policy.py`:

```python
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
```

- [ ] **Step 2: Run and verify RED**

```powershell
$env:PYTHONPATH = "src"
python -m unittest tests.test_policy -v
```

Expected: import failure because `models.py` and `policy.py` do not exist.

- [ ] **Step 3: Implement the message model**

Create `src/wechat_robot/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    message_type: int
    sender_id: str
    room_id: str
    content: str
    from_group: bool
    from_self: bool
    mentions_bot: bool
    bot_alias: str
```

- [ ] **Step 4: Implement the policy minimally**

Create `src/wechat_robot/policy.py`:

```python
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
```

- [ ] **Step 5: Run all tests and verify GREEN**

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Expected: configuration and policy tests all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wechat_robot/models.py src/wechat_robot/policy.py tests/test_policy.py
git commit -m "feat: authorize and rate-limit broadcasts"
```

### Task 4: Add Broadcast Orchestration With TDD

**Files:**
- Create: `src/wechat_robot/service.py`
- Create: `tests/test_service.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_service.py`:

```python
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
```

- [ ] **Step 2: Run and verify RED**

```powershell
$env:PYTHONPATH = "src"
python -m unittest tests.test_service -v
```

Expected: import failure because `service.py` does not exist.

- [ ] **Step 3: Implement the service**

Create `src/wechat_robot/service.py`:

```python
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
```

- [ ] **Step 4: Run all tests and verify GREEN**

Run unittest discovery. Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wechat_robot/service.py tests/test_service.py
git commit -m "feat: relay approved group broadcasts"
```

### Task 5: Add the WeChatFerry Gateway With TDD

**Files:**
- Create: `src/wechat_robot/wcf_gateway.py`
- Create: `tests/test_wcf_gateway.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/test_wcf_gateway.py`:

```python
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
        with self.assertRaisesRegex(RuntimeError, "wxid"):
            WcfGateway(FakeClient(bot_id=""))

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
```

- [ ] **Step 2: Run and verify RED**

```powershell
$env:PYTHONPATH = "src"
python -m unittest tests.test_wcf_gateway -v
```

Expected: import failure because `wcf_gateway.py` does not exist.

- [ ] **Step 3: Implement the adapter with a lazy runtime import**

Create `src/wechat_robot/wcf_gateway.py`:

```python
from __future__ import annotations

from typing import Any

from .models import IncomingMessage


class WcfGateway:
    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            try:
                from wcferry import Wcf
            except ImportError as exc:
                raise RuntimeError(
                    'WeChatFerry is not installed. Run: python -m pip install -e ".[runtime]"'
                ) from exc
            client = Wcf(debug=False)
        self._client = client
        self._bot_id = str(self._client.get_self_wxid() or "")
        if not self._bot_id:
            raise RuntimeError("Cannot determine the logged-in WeChat account wxid")

    @property
    def bot_id(self) -> str:
        return self._bot_id

    def start(self) -> bool:
        return bool(self._client.enable_receiving_msg())

    def receiving(self) -> bool:
        return bool(self._client.is_receiving_msg())

    def receive(self) -> IncomingMessage:
        raw = self._client.get_msg()
        from_group = bool(raw.from_group())
        room_id = str(raw.roomid or "")
        alias = self._client.get_alias_in_chatroom(self._bot_id, room_id) if from_group else ""
        return IncomingMessage(
            message_type=int(raw.type),
            sender_id=str(raw.sender or ""),
            room_id=room_id,
            content=str(raw.content or ""),
            from_group=from_group,
            from_self=bool(raw.from_self()),
            mentions_bot=bool(raw.is_at(self._bot_id)) if from_group else False,
            bot_alias=str(alias or ""),
        )

    def broadcast_all(self, room_id: str, text: str) -> int:
        return int(self._client.send_text(f"@所有人\n{text}", room_id, "notify@all"))

    def close(self) -> None:
        self._client.cleanup()
```

- [ ] **Step 4: Run all tests and verify GREEN**

Run unittest discovery. Expected: all tests pass without installing WeChatFerry.

- [ ] **Step 5: Commit**

```powershell
git add src/wechat_robot/wcf_gateway.py tests/test_wcf_gateway.py
git commit -m "feat: connect WeChatFerry gateway"
```

### Task 6: Add the Runtime Loop and CLI With TDD

**Files:**
- Create: `src/wechat_robot/__main__.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing lifecycle tests**

Create `tests/test_main.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path
from queue import Empty

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
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.config_path = Path(temp_dir.name) / "config.json"
        self.config_path.write_text(json.dumps({
            "allowed_rooms": ["room@chatroom"],
            "allowed_senders": ["wxid_ok"],
            "cooldown_seconds": 10,
            "log_level": "INFO",
        }), encoding="utf-8")

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
```

- [ ] **Step 2: Run and verify RED**

```powershell
$env:PYTHONPATH = "src"
python -m unittest tests.test_main -v
```

Expected: import failure because `__main__.py` does not exist.

- [ ] **Step 3: Implement the CLI and loop**

Create `src/wechat_robot/__main__.py`:

```python
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from queue import Empty
from typing import Callable, Sequence

from .config import ConfigurationError, load_config
from .policy import BroadcastPolicy
from .service import BroadcastService, HandlingOutcome
from .wcf_gateway import WcfGateway


LOGGER = logging.getLogger("wechat_robot")


def run(config_path: Path, gateway_factory: Callable[[], WcfGateway] = WcfGateway) -> int:
    config = load_config(config_path)
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    gateway = gateway_factory()
    try:
        if not gateway.start():
            raise RuntimeError("WeChatFerry refused to enable message reception")
        service = BroadcastService(BroadcastPolicy(config), gateway)
        LOGGER.info("Bot started as %s", gateway.bot_id)
        while gateway.receiving():
            try:
                message = gateway.receive()
                result = service.handle(message)
                if result.outcome is HandlingOutcome.SENT:
                    LOGGER.info("Broadcast sent room=%s sender=%s", message.room_id, message.sender_id)
                elif result.outcome is HandlingOutcome.SEND_FAILED:
                    LOGGER.error(
                        "Broadcast failed room=%s sender=%s status=%s",
                        message.room_id,
                        message.sender_id,
                        result.send_status,
                    )
            except Empty:
                continue
            except Exception:
                LOGGER.exception("Failed to process one incoming message")
    except KeyboardInterrupt:
        LOGGER.info("Shutdown requested")
    finally:
        gateway.close()
    return 0


def main(
    argv: Sequence[str] | None = None,
    gateway_factory: Callable[[], WcfGateway] = WcfGateway,
) -> int:
    parser = argparse.ArgumentParser(description="Guarded WeChat group @all relay bot")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    args = parser.parse_args(argv)
    try:
        return run(args.config, gateway_factory)
    except (ConfigurationError, RuntimeError) as exc:
        logging.getLogger("wechat_robot").error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run all tests and verify GREEN**

Run unittest discovery. Expected: all tests pass with no warnings.

- [ ] **Step 5: Commit**

```powershell
git add src/wechat_robot/__main__.py tests/test_main.py
git commit -m "feat: run guarded WeChat receive loop"
```

### Task 7: Add Packaging, Documentation, License, and CI

**Files:**
- Create: `pyproject.toml`
- Create: `config.example.json`
- Create: `README.md`
- Create: `LICENSE`
- Create: `.github/workflows/tests.yml`
- Modify: `.gitignore`

- [ ] **Step 1: Add package metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "wechat-group-broadcast-bot"
version = "0.1.0"
description = "A guarded WeChat group @all relay bot built on WeChatFerry"
readme = "README.md"
requires-python = ">=3.10,<3.11"
license = { file = "LICENSE" }
authors = [{ name = "mashirosusu" }]
dependencies = []

[project.optional-dependencies]
runtime = ["wcferry==39.5.2.0"]

[project.scripts]
wechat-robot = "wechat_robot.__main__:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Add the sanitized example and ignore local state**

Create `config.example.json`:

```json
{
  "allowed_rooms": ["123456789@chatroom"],
  "allowed_senders": ["wxid_example"],
  "cooldown_seconds": 10,
  "log_level": "INFO"
}
```

Extend `.gitignore` with:

```gitignore
config.json
.venv/
__pycache__/
*.py[cod]
.coverage
.pytest_cache/
*.egg-info/
build/
dist/
```

- [ ] **Step 3: Write the README and MIT license**

README must contain these exact operational sections:

```markdown
# WechatRobot

将白名单用户在白名单微信群中发送的 `@机器人 话术` 转发为原生 `@所有人` 消息。

## 风险警告

本项目依赖非官方 PC 微信 Hook 工具 WeChatFerry，仅用于学习和自有测试环境。它可能因微信升级失效，也存在账号限制或封禁风险。请使用专用测试账号；本项目不能绕过微信原生群权限。

## 环境

- Windows 10/11
- Python 3.10
- PC 微信 3.9.12.51
- WeChatFerry 39.5.2.0

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[runtime]"
Copy-Item config.example.json config.json
```

编辑 `config.json`，填入允许使用的群 `roomid` 和触发人的 `wxid`。不要提交真实配置。

## 启动

先登录指定版本的 PC 微信，再运行：

```powershell
wechat-robot --config config.json
```

## 行为

只有同时满足群白名单、发送者白名单、真实 @ 机器人、文本消息和冷却限制的消息才会发送。成功消息格式为：

```text
@所有人
原话术
```

## 测试

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 人工验收

在测试群给机器人账号群管理员权限并确认客户端原生允许该账号选择 `@所有人`。使用白名单账号发送 `@机器人 测试通知`，确认群里只出现一条原生全员提醒；再验证非白名单账号、非白名单群和冷却期重复请求均不会发送。
```

Create `LICENSE`:

```text
MIT License

Copyright (c) 2026 mashirosusu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Add GitHub Actions**

Create `.github/workflows/tests.yml`:

```yaml
name: tests

on:
  push:
  pull_request:

jobs:
  unit-tests:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: python -m pip install -e .
      - run: python -m unittest discover -s tests -v
```

- [ ] **Step 5: Verify configuration safety and package metadata**

Run:

```powershell
git check-ignore config.json .firecrawl
git grep -n -E "wxid_[A-Za-z0-9]{6,}|[0-9]{6,}@chatroom" -- ':!config.example.json' ':!docs/superpowers/**'
python -m pip install -e .
python -m unittest discover -s tests -v
```

Expected: both local paths are ignored, secret scan prints nothing, editable installation succeeds, and all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore .github LICENSE README.md config.example.json pyproject.toml
git commit -m "docs: add Windows setup and CI"
```

### Task 8: Final Verification and Publication

**Files:** All changed project files.

- [ ] **Step 1: Run fresh full verification**

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check HEAD~1 HEAD
git status --short
```

Expected: all tests pass, compilation exits 0, diff check prints nothing, and the worktree is clean.

- [ ] **Step 2: Review requirements against the approved design**

Confirm every acceptance criterion in `docs/superpowers/specs/2026-08-27-wechat-group-broadcast-bot-design.md` has a test, documentation, or explicit manual acceptance step. Do not claim a real WeChat broadcast was verified unless a logged-in test account and test group were actually exercised.

- [ ] **Step 3: Push all commits**

```powershell
git push origin main
```

- [ ] **Step 4: Verify the public repository and CI**

```powershell
gh repo view mashirosusu/WechatRobot --json url,visibility,defaultBranchRef
gh run list --repo mashirosusu/WechatRobot --limit 3
```

Expected: public URL is returned, `main` is the default branch, and the latest tests workflow succeeds. If CI is still running, wait with `gh run watch <run-id> --repo mashirosusu/WechatRobot --exit-status` before reporting completion.
