# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, ClassVar

import attrs

from ..api import logger, models
from ..api.interfaces import (
    AbstractMtaMilterConnectionHandler,
    AbstractMtaMilterSession,
    MilterAppFactory,
)
from ..protocol import definitions
from ..protocol.exceptions import ProtocolViolation
from ..protocol.packet import Packet, PacketDecoder, encode_payload
from ..protocol.payload import Payload, PayloadDecoder
from .session import MtaMilterSession


class MtaMilterConnectionHandlerClosed(BaseException):
    ...


@attrs.define(auto_attribs=False)
class MtaMilterConnectionHandler(AbstractMtaMilterConnectionHandler):
    _connection_id: models.MilterServerConnectionID = attrs.field()
    _reader: asyncio.StreamReader = attrs.field()
    _writer: asyncio.StreamWriter = attrs.field()
    app_factory: MilterAppFactory = attrs.field()
    _server_on_close_cb: Callable[
        [models.MilterServerConnectionID], None
    ] = attrs.field()
    _keep_reading_packets_task: asyncio.Task[Any] = attrs.field(init=False)
    _session: AbstractMtaMilterSession = attrs.field(init=False)
    _closed: bool = attrs.field(init=False)
    logger: logging.LoggerAdapter[logging.Logger] = attrs.field(init=False)
    READER_CHUNK_SIZE: ClassVar[int] = (
        definitions.MAX_DATA_SIZE + definitions.BASE_LEN_BYTES
    )

    def __attrs_post_init__(self) -> None:
        self._closed = False
        self.logger = logger.ConnectionContextLogger().get(__name__)
        self._session = MtaMilterSession(
            socket_connection=self,  # pyright: ignore PylancereportGeneralTypeIssues
        )
        self._keep_reading_packets_task = asyncio.create_task(
            self.keep_reading_packets(), name=f"keep_reading_packets-{self.id.short}"
        )
        self._keep_reading_packets_task.add_done_callback(
            self._keep_reading_packets_task_done,
        )

    def _keep_reading_packets_task_done(self, _: asyncio.Future[Any]) -> None:
        writer, reader = self._writer, self._reader
        if not writer.is_closing():
            self.logger.warning(
                f"Reading packets task is done without having writer closed. {writer=}"
            )
        if not reader.at_eof():
            self.logger.warning(
                f"Reading packets task is done without reader at at_eof. {reader=}"
            )
        if reader.exception():
            self.logger.warning(
                "Reading packets task is done with reader "
                f"exception={reader.exception=!r}"
            )
        self.logger.debug(f"DISCONNECTED {reader=} {writer=}")

        task = self._keep_reading_packets_task
        if not task.cancelled() and (exception := task.exception()) is not None:
            self.logger.exception(
                "_keep_reading_packets_task_done: "
                "Got an exception in the connection keep_reading_packets task. "
                f"[task={task.get_name()}, {exception=}, cancelled={task.cancelled()}]",
                exc_info=exception,
            )

    def _cancel_reader_task(self) -> None:
        if self._keep_reading_packets_task.done():
            exception = self._keep_reading_packets_task.exception()
        else:
            exception = None
        self.logger.debug(
            "_cancel_reader_task: "
            f"{self._keep_reading_packets_task.done()=} "
            f"{self._keep_reading_packets_task.cancelled()=} "
            f"{exception=}"
        )
        if not self._keep_reading_packets_task.cancelled():
            self._keep_reading_packets_task.cancel()

    def session_error_callback(self, *, exception: BaseException) -> None:
        self.logger.exception(
            "Error callback in in MtaMilterSession",
            exc_info=exception,
        )
        self.logger.debug("_hl_error_callback: Cancelling the socket reader task")
        self._cancel_reader_task()

    @property
    def id(self) -> models.MilterServerConnectionID:
        return self._connection_id

    async def keep_reading_packets(self) -> None:
        assert not self._closed
        packet_decoder = PacketDecoder(
            connection_id=self.id,  # pyright: ignore PylancereportGeneralTypeIssues
        )
        payload_decoder = PayloadDecoder(
            connection_id=self.id,  # pyright: ignore PylancereportGeneralTypeIssues
        )
        while True:
            try:
                self.logger.debug(f"request to read {self.READER_CHUNK_SIZE} bytes")
                packet: Packet = await self._reader.read(self.READER_CHUNK_SIZE)
                if not len(packet):
                    if self._reader.at_eof():
                        raise MtaMilterConnectionHandlerClosed()
                    else:
                        raise RuntimeError(
                            "Should not reach here; reading 0 bytes with "
                            f"{self._reader.at_eof()=}"
                        )
                self.logger.debug(f"got {len(packet)=} bytes [{packet=!r}]")
                for payload in packet_decoder.decode(packet=packet):
                    command_class, command_data = payload_decoder.decode(
                        payload=payload
                    )
                    self.logger.debug(f"{command_class=} {command_data=}")
                    command = command_class(data_raw=command_data)
                    self._session.queue_command(command)
                else:
                    self.logger.debug("No payload from packet (yet)")
            except ProtocolViolation:
                self.logger.error(
                    "Protocol violation, going to close the connection.",
                    exc_info=True,
                )
                await self.close_bottom_up()
                break
            except MtaMilterConnectionHandlerClosed:
                self.logger.debug("Milter-MTA connection closed")
                await self.close_bottom_up()
                break
            except ConnectionResetError:
                self.logger.error(
                    "Milter-MTA connection reset unexpectedly. This may indicate a "
                    "protocol violation as observed from the MTA."
                )
                await self.close_bottom_up()
                break
            except asyncio.CancelledError:
                await self._close()
                break

    async def write_response(self, payload: Payload, *, drain: bool = False) -> None:
        packet = encode_payload(payload)
        self.logger.debug(f"writing packet len={len(packet)} {packet=!r}")
        self._writer.write(packet)
        if drain:
            await self._writer.drain()

    async def _close(self, *, cancel_reader_task: bool = True) -> None:
        self.logger.debug(f"close_top_down; going to {cancel_reader_task=}")
        if cancel_reader_task:
            self._cancel_reader_task()
            self.logger.debug("close_top_down; _cancel_reader_task done")
        if self._closed:
            self.logger.debug("close_top_down; Already closed this connection?")
            return

        self._closed = True
        self._server_on_close_cb(self.id)
        self.logger.debug(f"writing EOF if {self._writer.can_write_eof()=}")
        try:
            if self._writer.can_write_eof():
                self._writer.can_write_eof()
                self._writer.write_eof()
                await self._writer.drain()
            if not self._writer.is_closing():
                self._writer.close()
                await self._writer.wait_closed()
            else:
                self.logger.debug("Transport writer already marked as closed.")
        except Exception:
            self.logger.error("Error closing client writer, ignoring.", exc_info=True)

    async def close_bottom_up(self) -> None:
        self.logger.debug("close_bottom_up")
        await self._session.close_bottom_up()
        await self._close()

    async def close_top_down(self) -> None:
        self.logger.debug("close_top_down")
        await self._close()
