# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
from contextlib import ContextDecorator
from typing import TYPE_CHECKING, Any

import attrs

from ..api import logger
from ..api.interfaces import (
    AbstractMilterApp,
    AbstractMtaMilterConnectionHandler,
    AbstractMtaMilterSession,
    QueueEntry,
)
from ..protocol import commands, definitions, responses

if TYPE_CHECKING:
    import logging
    import types

QUEUE_READER_TIMEOUT_SECONDS_DEFAULT = 30


@attrs.define(kw_only=True)
class DoneEventContextManager(ContextDecorator):
    event: asyncio.Event
    logger: logging.LoggerAdapter[logging.Logger]

    def __enter__(self) -> None:
        pass

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        self.logger.debug("Setting queue item done_event")
        self.event.set()


@attrs.define(auto_attribs=False)
class MtaMilterSession(AbstractMtaMilterSession):
    _socket_connection: AbstractMtaMilterConnectionHandler = attrs.field()
    _incoming_command_queue: asyncio.Queue[QueueEntry | None] = attrs.field(
        factory=asyncio.Queue
    )
    _commands_consumer_task: asyncio.Task[Any] = attrs.field(init=False)
    _app: AbstractMilterApp = attrs.field(init=False)
    macros_per_stage: dict[definitions.MacroStage, dict[str, str]] = attrs.field(
        init=False, factory=dict
    )
    _last_macro_command: commands.DefineMacro | None = None
    all_macros: dict[str, str] = attrs.field(init=False, factory=dict)
    queue_reader_timeout_seconds: float = attrs.field(
        default=QUEUE_READER_TIMEOUT_SECONDS_DEFAULT
    )
    _pending_manipulations: list[responses.AbstractManipulation] = attrs.field(
        init=False, factory=list
    )
    _manipulations_sent: bool = False

    def __attrs_post_init__(self) -> None:
        self._closed = False
        self.logger = logger.ConnectionContextLogger().get(__name__)
        self._app = self._socket_connection.app_factory(session=self)
        self.logger.debug("Starting commands_consumer task")
        self._commands_consumer_task = asyncio.create_task(
            self._commands_consumer(),
            name=f"commands_consumer_task-{self._socket_connection.id_.short}",
        )
        self._commands_consumer_task.add_done_callback(self.commands_consumer_task_done)

    def commands_consumer_task_done(self, future: asyncio.Future[Any]) -> None:
        self.logger.debug(
            "task done! "
            f"[task={self._commands_consumer_task.get_name()}, "
            f"done={self._commands_consumer_task.done()}, "
            f"cancelled={self._commands_consumer_task.cancelled()}]"
        )
        if (exception := self._commands_consumer_task.exception()) is not None:
            self.logger.error(
                "Got an exception in the commands consumer task. "
                f"[task={self._commands_consumer_task.get_name()}, "
                f"exception={self._commands_consumer_task.exception()}, "
                f"cancelled={self._commands_consumer_task.cancelled()}]"
            )
            self._socket_connection.session_error_callback(exception=exception)

    def queue_command(self, command: commands.BaseCommand) -> asyncio.Event:
        if self._commands_consumer_task.done():
            raise RuntimeError(
                "Queue is not being read anymore! "
                f"[task={self._commands_consumer_task.get_name()}, "
                f"exception={self._commands_consumer_task.exception()}, "
                f"cancelled={self._commands_consumer_task.cancelled()}]"
            )
        self.logger.debug(f"queue_command: {command=}")
        self._incoming_command_queue.put_nowait(entry := QueueEntry(command=command))
        self.logger.debug(
            f"incoming_command_queue size={self._incoming_command_queue.qsize()}"
        )
        return entry.done_event

    async def _commands_consumer(self) -> None:
        last_macro_command: commands.DefineMacro | None = None
        while True:
            self.logger.debug(
                f"commands_consumer: going to read the queue {last_macro_command=}"
            )
            had_timeout = False
            read_queue_inner_task = asyncio.Task(
                self._incoming_command_queue.get(),
                name=f"read_queue_inner_task-{self._socket_connection.id_.short}",
            )
            try:
                queue_item = await asyncio.wait_for(
                    read_queue_inner_task,
                    timeout=self.queue_reader_timeout_seconds,
                )
            except asyncio.TimeoutError:
                self.logger.debug("timeout reading the command queue")
                had_timeout = True
                read_queue_inner_task.cancel()
                continue
            except asyncio.CancelledError:
                self.logger.debug(
                    "commands_consumer task cancelled! "
                    f"{read_queue_inner_task.cancelled()=}"
                )
                if not read_queue_inner_task.cancelled():
                    self._incoming_command_queue.put_nowait(None)
                    read_queue_inner_task.cancel()
                    self.logger.debug(f"{read_queue_inner_task.cancelled()=}")
                return

            self.logger.debug(f"commands_consumer: got {queue_item=}")
            if queue_item is None:
                self.logger.debug(
                    f"Got None on the incoming command queue. {had_timeout=}"
                )
                if had_timeout:
                    continue
                else:
                    return

            with DoneEventContextManager(
                event=queue_item.done_event, logger=self.logger
            ):
                await self._process_queue_item(queue_item)

    async def _process_queue_item(self, queue_item: QueueEntry) -> None:
        match queue_item.command:
            case commands.OptionsNegotiate():
                # This one is an exception to the rule; implemented here.
                await self.on_options_negotiate(queue_item.command)
            case commands.DefineMacro():
                # A second exception; let's save the macro data to attach later when the
                # actual command is seen (see below) and keep track of all macros seen
                # during the session.
                self.on_define_macro(queue_item.command)
                self._last_macro_command = queue_item.command
            case _:
                if self._last_macro_command is not None:
                    self._attach_macros_to_command(
                        command=queue_item.command,
                        last_macro_command=self._last_macro_command,
                    )
                    self._last_macro_command = None
                response = await self.handle_command_in_app(command=queue_item.command)
                if response is not None:
                    self.save_manipulations(manipulations=response.manipulations)

                # If it's End of Message, we have to send pending manipulations first.
                if isinstance(queue_item.command, commands.EndOfMessage):
                    assert response is not None
                    self._manipulations_sent = True
                    self.logger.debug(
                        f"Sending {len(self._pending_manipulations)} manipulations "
                        "before end_of_message response."
                    )
                    for manipulation_response in self._pending_manipulations:
                        await self._send_response(manipulation_response)
                if response is not None:
                    await self._send_response(response)

    def _attach_macros_to_command(
        self,
        *,
        command: commands.BaseCommand,
        last_macro_command: commands.DefineMacro | None,
    ) -> None:
        if (
            last_macro_command is not None
            and isinstance(
                command,
                commands.Connect
                | commands.Helo
                | commands.MailFrom
                | commands.RcptTo
                | commands.Data
                | commands.Header
                | commands.EndOfHeaders
                | commands.BodyChunk
                | commands.EndOfMessage
                | commands.Unknown,
            )
            and commands.DefineMacro.command_char_to_stage.get(command.command_char)
            == last_macro_command.stage
        ):
            command.macros = last_macro_command.macros.copy()

    async def _stop_commands_consumer(self) -> None:
        task = self._commands_consumer_task
        if task.done():
            exception = task.exception()
        else:
            exception = None
        self.logger.debug(
            f"_stop_commands_consumer [task={task.get_name()}, exception={exception}, "
            f"cancelled={task.cancelled()}]"
        )
        if not task.cancelled():
            task.cancel()
        try:
            await asyncio.wait_for(task, 0.1)
        except asyncio.TimeoutError:
            task.cancel()

    async def close_bottom_up(self) -> None:
        self.logger.debug("close_bottom_up")
        await self._stop_commands_consumer()
        await self._app.on_mta_close_connection()

    async def close_top_down(self) -> None:
        self.logger.debug("close_top_down")
        await self._socket_connection.close_top_down()
        await self._stop_commands_consumer()

    async def _send_response(
        self, response: responses.AbstractResponse | responses.AbstractManipulation
    ) -> None:
        await self._socket_connection.write_response(response.encode())

    async def on_options_negotiate(self, command: commands.OptionsNegotiate) -> None:
        self.logger.debug("on_options_negotiate")
        response = responses.OptionsNegotiateResponse(
            protocol_flags=self._app.protocol_flags,
            symbols_for_stage=self._app.symbols,
        )
        await self._send_response(response)

    def on_define_macro(self, command: commands.DefineMacro) -> None:
        self.logger.debug(f"on_define_macro {command.macros=}")
        self.macros_per_stage[command.stage] = command.macros.copy()
        for key, value in command.macros.items():
            self.all_macros[key] = value

    def save_manipulations(
        self, *, manipulations: list[responses.AbstractManipulation]
    ) -> None:
        if self._manipulations_sent:
            self.logger.warning(
                "Adding manipulations after End of Message callback is not allowed; "
                f"ignoring: {manipulations}."
            )
            return
        self.logger.debug(
            f"Adding {len(manipulations)} to current list of length "
            f"{len(self._pending_manipulations)}"
        )
        self._pending_manipulations.extend(manipulations)

    async def handle_command_in_app(
        self, command: commands.BaseCommand
    ) -> responses.AbstractResponse | None:
        self.logger.debug(f"handle_command_in_app {command=}")
        match command:
            case commands.Connect():
                return await self._app.on_connect(command)
            case commands.Helo():
                return await self._app.on_helo(command)
            case commands.MailFrom():
                return await self._app.on_mail_from(command)
            case commands.RcptTo():
                return await self._app.on_rcpt_to(command)
            case commands.Data():
                return await self._app.on_data(command)
            case commands.Header():
                return await self._app.on_header(command)
            case commands.EndOfHeaders():
                return await self._app.on_end_of_headers(command)
            case commands.BodyChunk():
                return await self._app.on_body_chunk(command)
            case commands.EndOfMessage():
                return await self._app.on_end_of_message(command)
            case commands.Unknown():
                return await self._app.on_unknown(command)
            case commands.Abort():
                await self._app.on_abort(command)
                return None
            case commands.Quit():
                await self._app.on_quit(command)
                return None
            case _:
                raise NotImplementedError(
                    f"Command {command.__class__.__name__} not implemented"
                )
