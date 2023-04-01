# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import enum
import functools
import logging
import signal
from typing import TYPE_CHECKING

import attrs

from purepythonmilter._version import __version__ as purepythonmilter_version
from purepythonmilter.api.models import MilterServerConnectionID, connection_id_context

from .connectionhandler import MtaMilterConnectionHandler

if TYPE_CHECKING:
    from purepythonmilter.api.interfaces import MilterAppFactory


logger = logging.getLogger(__name__)


@enum.unique
class MilterServerState(enum.Enum):
    INITIALIZING = enum.auto()
    STARTING = enum.auto()
    STARTED = enum.auto()
    STOPPING = enum.auto()
    STOPPED = enum.auto()


@attrs.define(kw_only=True)
class MilterServer:
    _connections: dict[
        MilterServerConnectionID, MtaMilterConnectionHandler
    ] = attrs.field(init=False, factory=dict)
    _state: MilterServerState = attrs.field(
        init=False, default=MilterServerState.INITIALIZING
    )
    _app_factory: MilterAppFactory

    async def start_server(self, *, host: str, port: int) -> None:
        logger.info(f"Purepythonmilter version {purepythonmilter_version} starting...")

        assert self._state in (
            MilterServerState.INITIALIZING,
            MilterServerState.STOPPED,
        )
        self._state = MilterServerState.STARTING

        def cancel_tasks_handler(signal: signal.Signals) -> None:
            logger.debug(f"Got {signal=}!")
            logger.info("Shutting down milter on shutdown signal...")
            tasks = asyncio.all_tasks()
            logger.debug(f"Cancelling {len(tasks)} task(s).")
            [task.cancel() for task in tasks]

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(
            signal.SIGINT, functools.partial(cancel_tasks_handler, signal.SIGINT)
        )
        loop.add_signal_handler(
            signal.SIGTERM, functools.partial(cancel_tasks_handler, signal.SIGTERM)
        )

        async with (
            srv := await asyncio.start_server(self.handle_connection, host, port)
        ):
            self._state = MilterServerState.STARTED
            _host, _port = srv.sockets[0].getsockname()
            logger.info(f"Server started, awaiting connections on {_host}:{_port}...")
            try:
                await srv.serve_forever()
            except asyncio.CancelledError:
                await self.shutdown()

    async def handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Called when the MTA initiates a connection to this Milter instance (TCP or Unix
        socket).
        """
        connection_id = MilterServerConnectionID.generate()
        peername: str = writer.get_extra_info("peername")
        logger.debug(
            f"{connection_id.short}: MTA connected. {peername=} {reader} {writer}"
        )

        # The connection_id should be set as a context variable local to the task of
        # handling the connection.
        # asyncio.create_task() will copy the context for us, see:
        # https://docs.python.org/3/library/contextvars.html#asyncio-support
        connection_id_context.set(connection_id)

        def server_on_close_cb(connection_id: MilterServerConnectionID) -> None:
            logger.debug("server_on_close_cb")
            del self._connections[connection_id]

        connection = MtaMilterConnectionHandler(
            reader=reader,  # pyright: ignore [reportGeneralTypeIssues]
            writer=writer,  # pyright: ignore [reportGeneralTypeIssues]
            app_factory=self._app_factory,
            connection_id=connection_id,  # pyright: ignore [reportGeneralTypeIssues] # noqa: E501
            server_on_close_cb=server_on_close_cb,  # pyright: ignore [reportGeneralTypeIssues] # noqa: E501
        )
        self._connections[connection_id] = connection

    async def shutdown(self) -> None:
        self._state = MilterServerState.STOPPING
        # Copy into list, or else the dict value reader may change during iteration.
        connections = list(self._connections.values())
        logger.debug(
            f"Shutting down, closing {len(connections)} connections. "
            f"[{self._connections=}]"
        )
        # TODO: let current connections finish gracefully first.
        # TODO: make this run in parallel in case there are many connections?
        for conn in connections:
            await conn.close_bottom_up()

        # Ugly loop to await the task_done_del_connection_cb has been called.
        for i in range(1, 51):
            if n_connections := len(self._connections):
                if i % 5 == 0:
                    logger.warning(f"Still {n_connections} pending connections...")
                logger.debug(f"{connections=}")
                await asyncio.sleep(0.001 * i)
            else:
                break

        logger.info("Milter shutdown complete.")
        self._state = MilterServerState.STOPPED
