# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import logging

import pytest

from purepythonmilter.examples.change_body.__main__ import change_body_milter
from purepythonmilter.server.milterserver import MilterServer

from ..conftest import assert_read, await_connection_count

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "start_testserver", [pytest.param(change_body_milter)], indirect=True
)
async def test_change_body(
    start_testserver: tuple[MilterServer, asyncio.StreamReader, asyncio.StreamWriter],
    caplog: pytest.LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
    full_conversation_packets: list[bytes],
) -> None:
    caplog.set_level(logging.WARNING)
    srv, reader, writer = start_testserver

    await await_connection_count(srv, count=1)

    for packet in full_conversation_packets[:10]:
        writer.write(packet)
    await writer.drain()

    data1 = await assert_read(
        reader,
        # empty set for MacroStage.END_OF_MESSAGE (5) as part of
        # OptionsNegotiateResponse
        until_seen=b"\x00\x00\x00\x05\x00",
    )
    assert b"foobar" not in data1

    writer.write(full_conversation_packets[10])
    await writer.drain()

    await assert_read(
        reader,
        until_seen=b"\x07bfoobar\x00\x00\x00\x01c",
    )

    for packet in full_conversation_packets[11:]:
        writer.write(packet)
    await writer.drain()

    writer.close()
    await writer.wait_closed()

    data_after_eom = await reader.read(-1)
    assert not data_after_eom

    await await_connection_count(srv, count=0)
    assert not [rec for rec in caplog.records if rec.levelno >= logging.INFO]
