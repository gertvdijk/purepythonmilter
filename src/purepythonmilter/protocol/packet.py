# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, TypeAlias

import attrs

from ..api import logger, models
from .definitions import BASE_LEN_BYTES, MAX_DATA_SIZE
from .exceptions import ProtocolViolationPacket

if TYPE_CHECKING:
    import logging
    from collections.abc import Generator

    from .payload import Payload


Packet: TypeAlias = bytes


@attrs.define(auto_attribs=False, kw_only=True)
class PacketDecoder:
    logger: logging.LoggerAdapter[logging.Logger] = attrs.field(init=False)
    _connection_id: models.MilterServerConnectionID = attrs.field()
    _data_so_far: bytes = attrs.field(default=b"")

    def __attrs_post_init__(self) -> None:
        self.logger = logger.ConnectionContextLogger().get(__name__)

    def decode(self, packet: Packet) -> Generator[Payload, None, None]:
        """
        May be called multiple times with (incomplete) Packets and generates assembled
        Payloads.
        """
        # [0:] to prevent bytes with length 1 turning into an int in Python.
        self._data_so_far += packet[0:]
        while self._data_so_far:
            if len(self._data_so_far) < BASE_LEN_BYTES:
                # The length of the payload data is indicated by an unsigned int encoded
                # as 4 bytes in the TCP segment. We should wait until we have received
                # at least that number of bytes.
                return
            claimed_payload_length = self._parse_payload_length()
            if len(self._data_so_far) - 4 < claimed_payload_length:
                return
            else:
                pos_beyond = claimed_payload_length + 4
                assembled_payload = self._data_so_far[4:pos_beyond]
                self._data_so_far = self._data_so_far[pos_beyond:]
                self.logger.debug(
                    f"{claimed_payload_length=} {len(assembled_payload)=} "
                    f"{len(self._data_so_far)=}"
                )
                yield assembled_payload

    def _parse_payload_length(self) -> int:
        (payload_length_unpacked_any,) = struct.unpack("!I", self._data_so_far[0:4])
        payload_length = int(payload_length_unpacked_any)

        self.logger.debug(f"MTA sent packet claiming {payload_length=} byte(s).")
        if payload_length == 0 or payload_length > MAX_DATA_SIZE:
            raise ProtocolViolationPacket(
                f"Invalid packet data length: {payload_length=} [boundaries: > 0, "
                f"< {MAX_DATA_SIZE}, "
                f"connection_id={self._connection_id.short}]"
            )
        return payload_length


def encode_payload(payload: Payload) -> Packet:
    data_length_bin = struct.pack("!I", len(payload))
    return Packet(data_length_bin + payload)
