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
                    LOGGER.info(
                        "Broadcast sent room=%s sender=%s",
                        message.room_id,
                        message.sender_id,
                    )
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
