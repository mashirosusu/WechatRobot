# WeChat Group Broadcast Bot Design

## Objective

Build a small Windows-hosted Python bot for a personal WeChat account. When an authorized user mentions the bot in an authorized group, the bot republishes the remaining text as a native `@所有人` message in the same group.

The project will be published as the public GitHub repository `mashirosusu/WechatRobot` on the `main` branch.

## Supported Environment

- Windows 10 or Windows 11
- Python 3.10
- PC WeChat 3.9.12.51
- A dedicated test WeChat account with native permission to use `@所有人` in each configured group
- WeChatFerry as the local PC WeChat adapter

WeChatFerry is an unofficial Hook-based integration. The README must clearly state its version coupling and account-ban risk. The bot cannot bypass native WeChat group permissions.

## Functional Requirements

The bot processes a message only when all of these conditions are true:

1. It is a group message.
2. It is a text message.
3. It was not sent by the bot itself.
4. The bot account is present in the message's actual mention list.
5. The group `roomid` is in the configured group allowlist.
6. The sender `wxid` is in the configured sender allowlist.
7. The same sender has not triggered a broadcast in the same group within the configured cooldown period.
8. Text remains after removing the bot mention and surrounding whitespace.

For an accepted message, the bot sends this payload to the original group:

```text
@所有人
<authorized user's remaining text>
```

The WeChatFerry call uses `aters="notify@all"` so that this is a native all-members mention rather than plain text.

## Configuration

Runtime configuration is read from a local JSON file. The real file is ignored by Git; the repository contains a safe example.

```json
{
  "allowed_rooms": ["123456789@chatroom"],
  "allowed_senders": ["wxid_example"],
  "cooldown_seconds": 10,
  "log_level": "INFO"
}
```

Rules:

- `allowed_rooms` must contain at least one non-empty room ID ending in `@chatroom`.
- `allowed_senders` must contain at least one non-empty sender ID.
- `cooldown_seconds` is an integer from 0 through 3600.
- `log_level` is one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- Unknown fields are rejected to expose configuration mistakes.

## Architecture

The implementation is split into focused units:

- `config.py`: parse and validate JSON configuration.
- `models.py`: small framework-independent incoming-message value object.
- `policy.py`: authorization, cooldown, and text extraction logic.
- `service.py`: coordinate policy decisions and outbound broadcasting through a gateway interface.
- `wcf_gateway.py`: isolate imports and calls specific to WeChatFerry.
- `__main__.py`: configure logging, start WeChatFerry, consume messages, and shut down cleanly.

The policy and service layers do not import WeChatFerry. Unit tests use an in-memory fake gateway and real policy code, so CI does not need to log in to WeChat.

## Message Flow

1. The runner starts WeChatFerry and obtains the current bot `wxid`.
2. It enables message reception and consumes the message queue.
3. The gateway converts a WeChatFerry `WxMsg` into the internal message model.
4. The policy evaluates the eight requirements in order.
5. To remove the trigger mention, the adapter supplies the bot's current display name or group alias and the policy removes only the matching leading mention token plus WeChat's mention separator.
6. The service sends `@所有人\n<text>` to the same `roomid` with `notify@all`.
7. Cooldown state is recorded only after WeChatFerry reports a successful send.

Cooldown state is intentionally in memory. Restarting the process resets it.

## Failure Handling

- Invalid or missing configuration prevents startup and prints a concise error.
- Failure to initialize WeChatFerry or determine the logged-in account prevents startup.
- A failure while receiving or processing one message is logged and does not terminate the receive loop.
- A nonzero WeChatFerry send status is logged as an error and does not consume the cooldown.
- Empty messages after mention removal are ignored.
- Signal and keyboard shutdown disable message reception and release the WeChatFerry client where supported.

Logs include event type, room ID, and sender ID but do not log authentication data. Normal informational logs do not include full message bodies.

## Testing Strategy

Unit tests cover:

- valid authorized broadcast;
- non-group messages;
- non-text messages;
- messages sent by the bot;
- messages that do not actually mention the bot;
- groups outside the allowlist;
- senders outside the allowlist;
- empty text after mention removal;
- mention removal using the bot's group alias;
- cooldown rejection and acceptance after expiry;
- failed sends not starting cooldown;
- configuration success and every validation rule.

GitHub Actions runs formatting-independent unit tests on Python 3.10 without logging in to WeChat. Real integration is verified manually with a dedicated test account and test group:

1. Give the bot account permission to use `@所有人`.
2. Add the group and tester IDs to local configuration.
3. Mention the bot with a short test message.
4. Confirm the group receives exactly one native `@所有人` message containing the test text.
5. Confirm unauthorized users and groups cannot trigger it.
6. Confirm a repeated request inside the cooldown is ignored.

## Repository Contents

The public repository will contain source code, tests, an example configuration, Windows setup instructions, risk disclosures, an MIT license, and GitHub Actions configuration. It will not contain WeChat account data, real `wxid` values, local WeChat binaries, Hook DLL binaries, or authentication material.

## Out of Scope

- Web management UI
- Database or persistent audit history
- AI rewriting or moderation of the user's text
- Image, file, voice, or video broadcasting
- Multiple simultaneously logged-in bot accounts
- Automatic group discovery or automatic permission changes
- Supporting arbitrary PC WeChat versions
- Bypassing WeChat permissions, rate limits, or safety controls

## Acceptance Criteria

- All unit tests pass on Python 3.10.
- The repository contains no real account identifiers or credentials.
- The startup command and configuration process are documented.
- An authorized mention in an authorized group produces one native `@所有人` message with the remaining text.
- Every rejected condition produces no outbound group message.
- The public GitHub repository is linked as `origin` and the committed `main` branch is pushed.
