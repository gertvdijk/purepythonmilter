# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

import pytest

from purepythonmilter.api.models import MilterServerConnectionID
from purepythonmilter.protocol.definitions import MAX_DATA_SIZE
from purepythonmilter.protocol.exceptions import ProtocolViolationPacket
from purepythonmilter.protocol.packet import Packet, PacketDecoder
from purepythonmilter.protocol.payload import Payload

if TYPE_CHECKING:
    from collections.abc import Sequence


def _assert_nothing_logged(records: Sequence[logging.LogRecord]) -> None:
    assert not [rec for rec in records if rec.levelno >= logging.INFO]


@pytest.fixture()
def decoder() -> PacketDecoder:
    connection_id = MilterServerConnectionID.generate()
    return PacketDecoder(
        connection_id=connection_id,  # pyright: ignore [reportGeneralTypeIssues]
    )


def test_decode_empty(decoder: PacketDecoder, caplog: pytest.LogCaptureFixture) -> None:
    payloads = list(decoder.decode(Packet(b"")))
    assert payloads == []
    _assert_nothing_logged(caplog.records)


def test_decode_simple(
    decoder: PacketDecoder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    packet_bytes = b"\x00\x00\x00\rO\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff"
    payloads = list(decoder.decode(Packet(packet_bytes)))
    assert payloads == [Payload(packet_bytes[4:])]
    _assert_nothing_logged(caplog.records)


def test_decode_chunks(
    decoder: PacketDecoder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    packet_bytes = b"\x00\x00\x00\rO\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff"
    # Beyond the length field, but before the end.
    payloads = list(decoder.decode(Packet(packet_bytes[:10])))
    assert payloads == []
    payloads = list(decoder.decode(Packet(packet_bytes[10:])))
    assert payloads == [Payload(packet_bytes[4:])]
    _assert_nothing_logged(caplog.records)


def test_decode_chunks_mini(
    decoder: PacketDecoder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    packet_bytes = b"\x00\x00\x00\rO\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff"
    # Before the length field finished.
    payloads = list(decoder.decode(Packet(packet_bytes[:2])))
    assert payloads == []
    payloads = list(decoder.decode(Packet(packet_bytes[2:])))
    assert payloads == [Payload(packet_bytes[4:])]
    _assert_nothing_logged(caplog.records)


def construct_bogus_packet(payload_length: int) -> Packet:
    return struct.pack("!I", payload_length) + b" " * payload_length


@pytest.mark.parametrize(
    "packet",
    [
        pytest.param(
            construct_bogus_packet(1),
            id="lower-boundary-one",
        ),
        pytest.param(
            construct_bogus_packet(MAX_DATA_SIZE),
            id="upper-boundary",
        ),
    ],
)
def test_decode_length_boundaries_valid(
    decoder: PacketDecoder,
    packet: Packet,
    caplog: pytest.LogCaptureFixture,
) -> None:
    list(decoder.decode(packet))
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "packet",
    [
        pytest.param(
            construct_bogus_packet(0),
            id="zero-invalid",
        ),
        pytest.param(
            construct_bogus_packet(MAX_DATA_SIZE + 1),
            id="over-limit",
        ),
    ],
)
def test_decode_length_boundaries_invalid(
    decoder: PacketDecoder,
    packet: Packet,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ProtocolViolationPacket):
        list(decoder.decode(packet))
    _assert_nothing_logged(caplog.records)
