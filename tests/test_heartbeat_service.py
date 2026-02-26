import asyncio
from unittest.mock import AsyncMock

import pytest

from nanobot.heartbeat.service import HeartbeatService


async def test_start_is_idempotent(tmp_path) -> None:
    provider = AsyncMock()
    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="test-model",
        interval_s=9999,
        enabled=True,
    )

    await service.start()
    first_task = service._task
    await service.start()

    assert service._task is first_task

    service.stop()
    await asyncio.sleep(0)


async def test_start_disabled(tmp_path) -> None:
    provider = AsyncMock()
    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="test-model",
        interval_s=9999,
        enabled=False,
    )

    await service.start()
    assert service._task is None
