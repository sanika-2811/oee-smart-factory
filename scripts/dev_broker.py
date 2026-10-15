"""Tiny pure-Python MQTT broker (amqtt) for machines without Docker/Mosquitto - dev + tests only.

    python scripts/dev_broker.py            # tcp :1883 and websockets :9001

In production / Docker Compose the real Eclipse Mosquitto broker is used (deploy/mosquitto.conf).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

from amqtt.broker import Broker

CONFIG = {
    "listeners": {
        "default": {"type": "tcp", "bind": f"127.0.0.1:{os.environ.get('MQTT_TCP_PORT', '1883')}"},
        "ws": {"type": "ws", "bind": f"127.0.0.1:{os.environ.get('MQTT_WS_PORT', '9001')}"},
    },
    "sys_interval": 0,
    "auth": {"allow-anonymous": True, "plugins": ["auth_anonymous"]},
    "topic-check": {"enabled": False},
}


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    broker = Broker(CONFIG)
    await broker.start()
    print("dev MQTT broker up: tcp 1883, websockets 9001", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await broker.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
