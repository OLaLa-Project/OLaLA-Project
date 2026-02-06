from __future__ import annotations

import asyncio

import pytest

from app.core.async_utils import run_async_in_sync


async def _mul_two(value: int) -> int:
    await asyncio.sleep(0)
    return value * 2


def test_run_async_in_sync_without_running_loop() -> None:
    assert run_async_in_sync(_mul_two, 4) == 8


@pytest.mark.asyncio
async def test_run_async_in_sync_with_running_loop() -> None:
    # Called from within an active event loop; should execute via background thread safely.
    assert run_async_in_sync(_mul_two, 7) == 14
