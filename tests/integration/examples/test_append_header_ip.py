# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import logging

import pytest

from purepythonmilter.examples.append_header_ip.__main__ import append_header_ip_milter
from purepythonmilter.server.milterserver import MilterServer

from ..conftest import assert_read, await_connection_count

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "start_testserver", [pytest.param(append_header_ip_milter)], indirect=True
)
async def test_append_header_ip(
    start_testserver: tuple[MilterServer, asyncio.StreamReader, asyncio.StreamWriter],
    caplog: pytest.LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
    full_conversation_packets: list[bytes],
) -> None:
    caplog.set_level(logging.WARNING)
    srv, reader, writer = start_testserver

    await await_connection_count(srv, count=1)

    for packet in full_conversation_packets[:2]:
        writer.write(packet)
    await writer.drain()

    data1 = await assert_read(reader, until_seen=b"\x00\x00\x00\x01c")
    assert b"hX-UNSET" not in data1

    for packet in full_conversation_packets[2:11]:
        writer.write(packet)
    await writer.drain()

    await assert_read(
        reader,
        until_seen=b"\x00\x00\x00\x14hX-UNSET\x00172.17.0.1\x00\x00\x00\x00\x01c",
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
