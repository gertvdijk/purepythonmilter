# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import types
import typing
from typing import TYPE_CHECKING, Any, ClassVar

import attrs

from purepythonmilter.protocol import commands, definitions, responses
from purepythonmilter.server import milterserver

from . import interfaces, logger, models

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable, Coroutine


class ProgrammingError(BaseException):
    ...


def symbols_dict_empty_factory() -> dict[definitions.MacroStage, set[str]]:
    return {stage: set() for stage in definitions.CustomizableMacroStages}


@attrs.define(kw_only=True)
class PurePythonMilter:
    # https://github.com/python/mypy/issues/6473
    name: str = attrs.field(default=__qualname__)  # type: ignore[name-defined]
    # Connection-context logger
    logger: logging.LoggerAdapter[logging.Logger] = attrs.field(init=False)

    # Hooks
    hook_on_connect: None | Callable[
        [commands.Connect], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.Connect], Coroutine[Any, Any, responses.VerdictOrContinue]
    ] = None
    hook_on_helo: None | Callable[
        [commands.Helo], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.Helo], Coroutine[Any, Any, responses.VerdictOrContinue]
    ] = None
    hook_on_mail_from: None | Callable[
        [commands.MailFrom], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.MailFrom], Coroutine[Any, Any, responses.VerdictOrContinue]
    ] = None
    hook_on_rcpt_to: None | Callable[
        [commands.RcptTo], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.RcptTo], Coroutine[Any, Any, responses.VerdictOrContinue]
    ] = None
    on_rcpt_to_include_rejected: bool = False
    hook_on_data: None | Callable[
        [commands.Data], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.Data], Coroutine[Any, Any, responses.VerdictOrContinue]
    ] = None
    hook_on_header: None | Callable[
        [commands.Header], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.Header], Coroutine[Any, Any, responses.VerdictOrContinue]
    ] = None
    hook_on_end_of_headers: None | Callable[
        [commands.EndOfHeaders], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.EndOfHeaders], Coroutine[Any, Any, responses.VerdictOrContinue]
    ] = None
    hook_on_body_chunk: None | Callable[
        [commands.BodyChunk], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.BodyChunk],
        Coroutine[Any, Any, responses.VerdictOrContinue | responses.SkipToNextStage],
    ] = None
    hook_on_end_of_message: None | Callable[
        [commands.EndOfMessage], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.EndOfMessage], Coroutine[Any, Any, responses.AbstractResponse]
    ] = None
    hook_on_abort: None | Callable[[commands.Abort], Coroutine[Any, Any, None]] = None
    hook_on_quit: None | Callable[[commands.Quit], Coroutine[Any, Any, None]] = None
    hook_on_unknown: None | Callable[
        [commands.Unknown], Coroutine[Any, Any, None]
    ] | Callable[
        [commands.Unknown], Coroutine[Any, Any, responses.VerdictOrContinue]
    ] = None

    # An empty set of symbols for a stage disables all macros sent for it.
    # If a stage is not included, the default set by the MTA will be set (=all).
    # So, to receive all the symbols, use `restrict_symbols=None`.
    restrict_symbols: dict[definitions.MacroStage, set[str]] | None = attrs.field(
        factory=symbols_dict_empty_factory
    )
    headers_with_leading_space: bool = False
    _milterserver: milterserver.MilterServer | None = attrs.field(
        init=False, default=None
    )

    # Manipulation flags
    can_add_headers: bool = False
    can_add_recipients: bool = False
    can_add_recipients_with_esmtp_args: bool = False
    can_change_body: bool = False
    can_change_headers: bool = False
    can_change_mail_from: bool = False
    can_remove_recipients: bool = False
    can_quarantine: bool = False

    _request_proto_flags: models.RequestProtocolFlags = attrs.field(
        init=False, factory=models.RequestProtocolFlags
    )

    def __attrs_post_init__(self) -> None:  # noqa: C901
        self.logger = logger.ConnectionContextLogger().get(self.name)
        if self.hook_on_connect is not None:
            self._request_proto_flags.call_connect = True
            self._request_proto_flags.reply_connect = self._hook_needs_reply(
                self.hook_on_connect
            )
        if self.hook_on_helo is not None:
            self._request_proto_flags.call_helo = True
            self._request_proto_flags.reply_helo = self._hook_needs_reply(
                self.hook_on_helo
            )
        if self.hook_on_mail_from is not None:
            self._request_proto_flags.call_mail_from = True
            self._request_proto_flags.reply_mail_from = self._hook_needs_reply(
                self.hook_on_mail_from
            )
        if self.hook_on_rcpt_to is not None:
            self._request_proto_flags.call_rcpt_to = True
            self._request_proto_flags.reply_rcpt_to = self._hook_needs_reply(
                self.hook_on_rcpt_to
            )
            self._request_proto_flags.call_rcpt_to_rejected = (
                self.on_rcpt_to_include_rejected
            )
        if self.hook_on_data is not None:
            self._request_proto_flags.call_data = True
            self._request_proto_flags.reply_data = self._hook_needs_reply(
                self.hook_on_data
            )
        if self.hook_on_header is not None:
            self._request_proto_flags.call_headers = True
            self._request_proto_flags.reply_headers = self._hook_needs_reply(
                self.hook_on_header
            )
        if self.hook_on_end_of_headers is not None:
            self._request_proto_flags.call_end_of_headers = True
            self._request_proto_flags.reply_end_of_headers = self._hook_needs_reply(
                self.hook_on_end_of_headers
            )
        if self.hook_on_body_chunk is not None:
            self._request_proto_flags.call_body_chunk = True
            self._request_proto_flags.reply_body_chunk = self._hook_needs_reply(
                self.hook_on_body_chunk
            )
        # Note: responses cannot be disabled/enabled to End of message (always enabled),
        # Abort (always disabled) and Quit (always disabled).
        if self.hook_on_unknown is not None:
            self._request_proto_flags.call_unknown = True
            self._request_proto_flags.reply_unknown = self._hook_needs_reply(
                self.hook_on_unknown
            )
        self._request_proto_flags.can_specify_macros = bool(self.restrict_symbols)
        if self.restrict_symbols is None:
            self.restrict_symbols = {}
        self._request_proto_flags.headers_with_leading_space = (
            self.headers_with_leading_space
        )
        self._request_proto_flags.can_add_headers = self.can_add_headers
        self._request_proto_flags.can_add_recipients = self.can_add_recipients
        self._request_proto_flags.can_add_recipients_with_esmtp_args = (
            self.can_add_recipients_with_esmtp_args
        )
        self._request_proto_flags.can_change_body = self.can_change_body
        self._request_proto_flags.can_change_headers = self.can_change_headers
        self._request_proto_flags.can_change_mail_from = self.can_change_mail_from
        self._request_proto_flags.can_remove_recipients = self.can_remove_recipients
        self._request_proto_flags.can_quarantine = self.can_quarantine

    def _hook_needs_reply(
        self,
        hook: Callable[[Any], Any],
    ) -> bool:
        hints = typing.get_type_hints(hook)
        if "return" not in hints:
            raise ProgrammingError(
                f"Please annotate the return type for hook {hook.__name__}()."
            )
        # Fails flake8 check, but isinstance check on NoneType is not working.
        return hints.get("return") is not types.NoneType  # noqa: E721

    def _get_factory(self) -> interfaces.MilterAppFactory:  # noqa: C901
        """
        Create a factory for the connection handler to call on every new connection.
        Instead of this being the factory, the "factory of factory" pattern allows for
        passing parameters not known / not relevant at this level.
        """
        hook_on_connect = self.hook_on_connect
        hook_on_helo = self.hook_on_helo
        hook_on_mail_from = self.hook_on_mail_from
        hook_on_rcpt_to = self.hook_on_rcpt_to
        hook_on_data = self.hook_on_data
        hook_on_header = self.hook_on_header
        hook_on_end_of_headers = self.hook_on_end_of_headers
        hook_on_body_chunk = self.hook_on_body_chunk
        hook_on_end_of_message = self.hook_on_end_of_message
        hook_on_abort = self.hook_on_abort
        hook_on_quit = self.hook_on_quit
        hook_on_unknown = self.hook_on_unknown
        logger_name_ = self.name
        request_proto_flags = self._request_proto_flags
        assert self.restrict_symbols is not None
        symbols_ = self.restrict_symbols

        class BaseMilter(interfaces.AbstractMilterApp):
            logger_name: ClassVar[str] = logger_name_
            protocol_flags: ClassVar[models.RequestProtocolFlags] = request_proto_flags
            symbols: ClassVar[dict[definitions.MacroStage, set[str]]] = symbols_

            def __init__(self, *, session: interfaces.AbstractMtaMilterSession) -> None:
                self._session = session
                self.logger = logger.ConnectionContextLogger().get(self.logger_name)

            async def on_connect(
                self, command: commands.Connect
            ) -> responses.VerdictOrContinue | None:
                if hook_on_connect is None:
                    return None
                # Have to add specific type in assignment here or else reveal_type()
                # shows this as Any? 🤔
                ret: responses.VerdictOrContinue | None = await hook_on_connect(command)
                return ret

            async def on_helo(
                self, command: commands.Helo
            ) -> responses.VerdictOrContinue | None:
                if hook_on_helo is None:
                    return None
                ret: responses.VerdictOrContinue | None = await hook_on_helo(command)
                return ret

            async def on_mail_from(
                self, command: commands.MailFrom
            ) -> responses.VerdictOrContinue | None:
                if hook_on_mail_from is None:
                    return None
                ret: responses.VerdictOrContinue | None = await hook_on_mail_from(
                    command
                )
                return ret

            async def on_rcpt_to(
                self, command: commands.RcptTo
            ) -> responses.VerdictOrContinue | None:
                if hook_on_rcpt_to is None:
                    return None
                ret: responses.VerdictOrContinue | None = await hook_on_rcpt_to(command)
                return ret

            async def on_data(
                self, command: commands.Data
            ) -> responses.VerdictOrContinue | None:
                if hook_on_data is None:
                    return None
                ret: responses.VerdictOrContinue | None = await hook_on_data(command)
                return ret

            async def on_header(
                self, command: commands.Header
            ) -> responses.VerdictOrContinue | None:
                if hook_on_header is None:
                    return None
                ret: responses.VerdictOrContinue | None = await hook_on_header(command)
                return ret

            async def on_end_of_headers(
                self, command: commands.EndOfHeaders
            ) -> responses.VerdictOrContinue | None:
                if hook_on_end_of_headers is None:
                    return None
                ret: responses.VerdictOrContinue | None = await hook_on_end_of_headers(
                    command
                )
                return ret

            async def on_body_chunk(
                self, command: commands.BodyChunk
            ) -> responses.VerdictOrContinue | responses.SkipToNextStage | None:
                if hook_on_body_chunk is None:
                    return None
                ret: responses.VerdictOrContinue | responses.SkipToNextStage | None = (
                    await hook_on_body_chunk(command)
                )
                return ret

            async def on_end_of_message(
                self, command: commands.EndOfMessage
            ) -> responses.AbstractResponse:
                # Note: ensures that a None-response by the app gets translated into a
                # Continue response.
                if hook_on_end_of_message is None:
                    return responses.Continue()
                ret: responses.AbstractResponse | None = await hook_on_end_of_message(
                    command
                )
                if ret is None:
                    return responses.Continue()
                return ret

            async def on_abort(self, command: commands.Abort) -> None:
                if hook_on_abort is not None:
                    await hook_on_abort(command)

            async def on_quit(self, command: commands.Quit) -> None:
                if hook_on_quit is not None:
                    await hook_on_quit(command)

            async def on_unknown(
                self, command: commands.Unknown
            ) -> responses.VerdictOrContinue | None:
                if hook_on_unknown is None:
                    return None
                ret: responses.VerdictOrContinue | None = await hook_on_unknown(command)
                return ret

            async def on_mta_close_connection(self) -> None:
                self.logger.debug("on_mta_close_connection")

            async def close_connection(self) -> None:
                self.logger.debug("close_connection")

            async def send_progress(self) -> None:
                self.logger.debug("send_progress")

        return BaseMilter

    async def start_server(self, *, host: str, port: int) -> None:
        if self._milterserver:
            raise RuntimeError("You can only start this app once.")
        srv = milterserver.MilterServer(
            app_factory=self._get_factory()  # pyright: ignore [reportGeneralTypeIssues] # noqa: E501
        )
        self._milterserver = srv
        await srv.start_server(host=host, port=port)
        self._milterserver = None

    def run_server(self, *, host: str, port: int) -> None:
        asyncio.run(self.start_server(host=host, port=port))
