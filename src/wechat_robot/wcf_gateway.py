from __future__ import annotations

from typing import Any

from .models import IncomingMessage


class WcfGateway:
    """Small adapter around WeChatFerry's client API."""

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
        alias = (
            self._client.get_alias_in_chatroom(self._bot_id, room_id)
            if from_group
            else ""
        )
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
