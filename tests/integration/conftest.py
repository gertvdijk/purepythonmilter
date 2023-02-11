# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from purepythonmilter.api.application import PurePythonMilter
    from purepythonmilter.server.milterserver import MilterServer

    class FixtureRequest:
        param: PurePythonMilter

else:
    from typing import Any

    FixtureRequest = Any


pytestmark = pytest.mark.asyncio

logger = logging.getLogger(__name__)

HOST_LOCALHOST = "127.0.0.1"


async def assert_read(
    reader: asyncio.StreamReader, *, until_seen: bytes, timeout_ms: int = 1000
) -> bytes:
    bytes_read = b""
    start = time.time()
    for _ in range(0, timeout_ms):
        if time.time() - start > (float(timeout_ms) / 1000):
            break
        try:
            bytes_read += await asyncio.wait_for(reader.read(1000), 0.001)
        except asyncio.TimeoutError:
            continue
        if until_seen in bytes_read:
            return bytes_read
        await asyncio.sleep(0.001)

    raise RuntimeError(
        f"Did not read expected {until_seen!r} within {timeout_ms=}, {bytes_read=!r}."
    )


async def assert_reader_closed(
    reader: asyncio.StreamReader, *, timeout_ms: int = 1000
) -> bytes:
    bytes_read = b""
    start = time.time()
    for _ in range(0, timeout_ms):
        if time.time() - start > (float(timeout_ms) / 1000):
            break
        try:
            bytes_read += await asyncio.wait_for(reader.read(-1), 0.001)
        except asyncio.TimeoutError:
            continue
        if reader.at_eof():
            return bytes_read
        await asyncio.sleep(0.001)

    raise RuntimeError(
        f"Did not reach expected reader.at_eof() within {timeout_ms=}, {bytes_read=!r}."
    )


async def await_connection_count(
    srv: MilterServer, *, count: int, timeout_ms: int = 1000
) -> None:
    for _ in range(0, timeout_ms):
        if len(srv._connections) == count:
            break
        await asyncio.sleep(0.001)
    else:
        raise RuntimeError(
            f"Did not see expected connection {count=} within {timeout_ms=}."
        )


async def _await_startup(
    port: int,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    for _ in range(0, 1000):
        await asyncio.sleep(0.001)
        logger.info("checking if server is accepting connections already...")
        try:
            reader, writer = await asyncio.open_connection(HOST_LOCALHOST, port)
        except ConnectionRefusedError:
            logger.info("no, will check again...")
            continue
        else:
            return reader, writer
    else:
        raise RuntimeError("Server not accepting connections")


async def _await_shutdown(server_task: asyncio.Task[None]) -> None:
    for _ in range(0, 1000):
        await asyncio.sleep(0.001)
        logger.info("checking if server is shut down...")
        if server_task.done():
            logger.info("yes, done!")
            break
        logger.info("no, will check again...")


@pytest.fixture()
def start_testserver(
    request: FixtureRequest,  # indirect parameter to specify app factory
    event_loop: asyncio.AbstractEventLoop,
    unused_tcp_port: int,
    caplog: pytest.LogCaptureFixture,
) -> Generator[
    tuple[MilterServer, asyncio.StreamReader, asyncio.StreamWriter], None, None
]:
    app = request.param
    server_task = asyncio.ensure_future(
        app.start_server(host=HOST_LOCALHOST, port=unused_tcp_port), loop=event_loop
    )
    reader, writer = event_loop.run_until_complete(_await_startup(unused_tcp_port))
    assert app._milterserver is not None

    try:
        yield app._milterserver, reader, writer
    finally:
        server_task.cancel()
        event_loop.run_until_complete(_await_shutdown(server_task))
        assert not [rec for rec in caplog.records if rec.levelno >= logging.WARNING]
