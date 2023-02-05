# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import logging

import pytest

from purepythonmilter.api.application import PurePythonMilter
from purepythonmilter.protocol import commands
from purepythonmilter.server.milterserver import MilterServer

from .conftest import assert_read, assert_reader_closed, await_connection_count

pytestmark = pytest.mark.asyncio

logger = logging.getLogger(__name__)
HOST_LOCALHOST = "127.0.0.1"


on_connect_call_seen: commands.BaseCommand | None = None


async def on_connect(cmd: commands.Connect) -> None:
    global on_connect_call_seen
    on_connect_call_seen = cmd


mytestmilter_on_connect = PurePythonMilter(
    name="mytestmilter_on_connect",
    hook_on_connect=on_connect,
)

mytestmilter_no_hooks = PurePythonMilter(name="mytestmilter_no_hooks")


@pytest.mark.parametrize(
    "start_testserver", [pytest.param(mytestmilter_on_connect)], indirect=True
)
async def test_server_basic(
    start_testserver: tuple[MilterServer, asyncio.StreamReader, asyncio.StreamWriter],
    caplog: pytest.LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
    full_conversation_packets: list[bytes],
) -> None:
    global on_connect_call_seen
    caplog.set_level(logging.WARNING)
    srv, reader, writer = start_testserver
    await await_connection_count(srv, count=1)

    for packet in full_conversation_packets[:1]:
        writer.write(packet)
    await writer.drain()
    await assert_read(reader, until_seen=b"O")

    for packet in full_conversation_packets[1:11]:
        writer.write(packet)
    await writer.drain()
    data_until_eom = await assert_read(reader, until_seen=b"\x00\x00\x00\x01c")
    assert data_until_eom == b"\x00\x00\x00\x01c"
    assert isinstance(on_connect_call_seen, commands.Connect)

    for packet in full_conversation_packets[11:]:
        writer.write(packet)
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    assert not await reader.read(-1)

    await await_connection_count(srv, count=0)

    assert not [rec for rec in caplog.records if rec.levelno >= logging.WARNING]
    on_connect_call_seen = None


@pytest.mark.parametrize(
    "start_testserver", [pytest.param(mytestmilter_no_hooks)], indirect=True
)
async def test_server_basic_nohooks(
    start_testserver: tuple[MilterServer, asyncio.StreamReader, asyncio.StreamWriter],
    caplog: pytest.LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
    full_conversation_packets: list[bytes],
) -> None:
    srv, reader, writer = start_testserver
    await await_connection_count(srv, count=1)

    for packet in full_conversation_packets[:1]:
        writer.write(packet)
    await writer.drain()
    await assert_read(reader, until_seen=b"O")

    for packet in full_conversation_packets[1:11]:
        writer.write(packet)
    await writer.drain()
    data_until_eom = await assert_read(reader, until_seen=b"\x00\x00\x00\x01c")
    assert data_until_eom == b"\x00\x00\x00\x01c"

    for packet in full_conversation_packets[11:]:
        writer.write(packet)
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    assert not await reader.read(-1)

    await await_connection_count(srv, count=0)

    assert not [rec for rec in caplog.records if rec.levelno >= logging.WARNING]


@pytest.mark.parametrize(
    "start_testserver", [pytest.param(mytestmilter_on_connect)], indirect=True
)
async def test_server_protocol_violation_close_connection(
    start_testserver: tuple[MilterServer, asyncio.StreamReader, asyncio.StreamWriter],
    caplog: pytest.LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
) -> None:
    global on_connect_call_seen
    caplog.set_level(logging.WARNING)
    srv, reader, writer = start_testserver
    await await_connection_count(srv, count=1)

    options_negotiate_packet = (
        b"\xf0\x00\x00\rO\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff"
    )
    writer.write(options_negotiate_packet)
    await writer.drain()
    data_until_closed = await assert_reader_closed(reader)
    assert not data_until_closed

    assert on_connect_call_seen is None

    warnings = [rec for rec in caplog.records if rec.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert "Protocol violation, going to close the connection." in warnings[0].message
    on_connect_call_seen = None
