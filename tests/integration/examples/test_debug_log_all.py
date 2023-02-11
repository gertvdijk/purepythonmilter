# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# pyright: reportPrivateUsage=false
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from purepythonmilter.examples.debug_log_all.__main__ import debug_log_all_milter

from ..conftest import assert_read, await_connection_count

if TYPE_CHECKING:
    import asyncio

    from purepythonmilter.server.milterserver import MilterServer


pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "start_testserver", [pytest.param(debug_log_all_milter)], indirect=True
)
async def test_debug_log_all(
    start_testserver: tuple[MilterServer, asyncio.StreamReader, asyncio.StreamWriter],
    caplog: pytest.LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
    full_conversation_packets: list[bytes],
) -> None:
    caplog.set_level(logging.WARNING)
    srv, reader, writer = start_testserver

    await await_connection_count(srv, count=1)

    for packet in full_conversation_packets[:1]:
        writer.write(packet)
    await writer.drain()

    await assert_read(reader, until_seen=b"O\x00\x00\x00\x06")

    for packet in full_conversation_packets[1:11]:
        writer.write(packet)
    await writer.drain()

    data_connect_to_eom = await assert_read(reader, until_seen=b"\x00\x00\x00\x01c")
    assert data_connect_to_eom == b"\x00\x00\x00\x01c"

    for packet in full_conversation_packets[11:]:
        writer.write(packet)
    await writer.drain()

    writer.close()
    await writer.wait_closed()

    data_after_eom = await reader.read(-1)
    assert not data_after_eom

    await await_connection_count(srv, count=0)
    assert not [rec for rec in caplog.records if rec.levelno >= logging.INFO]
