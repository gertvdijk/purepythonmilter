# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import abc
import asyncio
import logging
import typing

import attrs

from purepythonmilter.protocol import definitions
from purepythonmilter.protocol.responses import AbstractResponse

from ..api.models import MilterServerConnectionID, RequestProtocolFlags
from ..protocol import commands, payload, responses


class AbstractMtaMilterConnectionHandler(abc.ABC):
    _connection_id: MilterServerConnectionID
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    app_factory: MilterAppFactory
    _session: AbstractMtaMilterSession
    _closed: bool
    logger: logging.LoggerAdapter[logging.Logger]

    @property
    @abc.abstractmethod
    def id(self) -> MilterServerConnectionID:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def keep_reading_packets(self) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def write_response(
        self, payload: payload.Payload, *, drain: bool = False
    ) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def close_bottom_up(self) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def close_top_down(self) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    def session_error_callback(self, *, exception: BaseException) -> None:
        ...  # pragma: nocover


@attrs.define(kw_only=True)
class QueueEntry:
    command: commands.BaseCommand
    done_event: asyncio.Event = attrs.field(factory=asyncio.Event)


class AbstractMtaMilterSession(abc.ABC):
    _socket_connection: AbstractMtaMilterConnectionHandler
    _incoming_command_queue: asyncio.Queue[QueueEntry | None]
    _commands_consumer_task: asyncio.Task[typing.Any]
    _app: AbstractMilterApp

    @abc.abstractmethod
    async def on_options_negotiate(self, command: commands.OptionsNegotiate) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    def queue_command(self, command: commands.BaseCommand) -> asyncio.Event:
        """
        Queues the command, returns an Event which will be set on completion of the
        processing including writing the response data (or exception thrown on error).

            done_event = queue_command(cmd)
            await done_event.wait()
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    async def _commands_consumer(self) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def _send_response(self, response: AbstractResponse) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def close_bottom_up(self) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def close_top_down(self) -> None:
        ...  # pragma: nocover


class AbstractMilterApp(abc.ABC):
    _session: AbstractMtaMilterSession
    protocol_flags: typing.ClassVar[RequestProtocolFlags]
    symbols: typing.ClassVar[dict[definitions.MacroStage, set[str]]]

    @abc.abstractmethod
    async def on_connect(
        self, command: commands.Connect
    ) -> responses.VerdictOrContinue | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_helo(
        self, command: commands.Helo
    ) -> responses.VerdictOrContinue | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_mail_from(
        self, command: commands.MailFrom
    ) -> responses.VerdictOrContinue | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_rcpt_to(
        self, command: commands.RcptTo
    ) -> responses.VerdictOrContinue | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_data(
        self, command: commands.Data
    ) -> responses.VerdictOrContinue | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_header(
        self, command: commands.Header
    ) -> responses.VerdictOrContinue | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_end_of_headers(
        self, command: commands.EndOfHeaders
    ) -> responses.VerdictOrContinue | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_body_chunk(
        self, command: commands.BodyChunk
    ) -> responses.VerdictOrContinue | responses.SkipToNextStage | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_end_of_message(
        self, command: commands.EndOfMessage
    ) -> responses.AbstractResponse:
        """
        End of message callback is always called and requires a final response as
        mandated by the protocol.
        Returning None from the hook should imply a Continue Response (including pending
        message manipulations).
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_abort(self, command: commands.Abort) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_quit(self, command: commands.Quit) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_unknown(
        self, command: commands.Unknown
    ) -> responses.VerdictOrContinue | None:
        ...  # pragma: nocover

    @abc.abstractmethod
    async def on_mta_close_connection(self) -> None:
        """Called when closing the chain bottom-up."""
        ...  # pragma: nocover

    @abc.abstractmethod
    async def close_connection(self) -> None:
        """Request to close the Milter connection; top-down the chain."""
        ...  # pragma: nocover

    @abc.abstractmethod
    async def send_progress(self) -> None:
        """Send an intermediate Progress response."""
        ...  # pragma: nocover


class MilterAppFactory(typing.Protocol):
    @staticmethod
    def __call__(*, session: AbstractMtaMilterSession) -> AbstractMilterApp:
        ...  # pragma: nocover
