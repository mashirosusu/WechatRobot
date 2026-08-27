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
