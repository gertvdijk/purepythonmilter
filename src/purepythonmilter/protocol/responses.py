# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import abc
import logging
import struct
from typing import TYPE_CHECKING, ClassVar, Literal, TypeAlias

import attrs

from purepythonmilter.api import logger, models

from . import definitions
from .payload import Payload

if TYPE_CHECKING:
    from collections.abc import Iterable


ResponseData: TypeAlias = bytes


@attrs.define(auto_attribs=False, kw_only=True)
class AbstractBaseResponse(abc.ABC):
    response_char: ClassVar[bytes]
    logger: logging.LoggerAdapter[logging.Logger] = attrs.field(
        init=False, eq=False, repr=False
    )

    def __attrs_post_init__(self) -> None:
        self.logger = logger.ConnectionContextLogger().get(__name__)

    @abc.abstractmethod
    def encode(self) -> Payload:
        ...  # pragma: nocover

    def __str__(self) -> str:
        return f"{self.__class__.__name__} response"


class AbstractManipulation(AbstractBaseResponse):
    pass


@attrs.define(auto_attribs=False, kw_only=True)
class AbstractResponse(AbstractBaseResponse):
    # All manipulations will be saved up until the End of Message callback.
    manipulations: list[AbstractManipulation] = attrs.field(factory=list)


class AbstractVerdict(AbstractResponse):
    def __str__(self) -> str:
        return f"{self.__class__.__name__} (verdict)"


class BaseResponseNoData(AbstractResponse):
    def encode(self) -> Payload:
        return Payload(self.response_char)


class BaseVerdictNoData(BaseResponseNoData, AbstractVerdict):
    pass


@attrs.define(auto_attribs=False, kw_only=True)
class OptionsNegotiateResponse(AbstractResponse):
    """
    Only during options negotiation you can send the requested symbols for each command.
    """

    # No SMFIR_* definition available; seems to be the same as with command from server.
    response_char: ClassVar[bytes] = b"O"
    protocol_version = definitions.VERSION
    protocol_flags: models.RequestProtocolFlags = attrs.field()
    symbols_for_stage: dict[definitions.MacroStage, set[str]] = attrs.field(
        factory=dict
    )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    @classmethod
    def _encode_symbols_list(
        cls,
        stage: definitions.MacroStage,
        symbols: Iterable[str],
    ) -> bytes:
        return (
            struct.pack("!I", stage.value)
            + b" ".join([(s.encode("utf-8")) for s in sorted(symbols)])
            + b"\x00"
        )

    def _log_flags_table(self, *, protocol_flags: int, action_flags: int) -> None:
        self.logger.debug(
            "Encoded options negotiate response flags "
            f"[version={self.protocol_version=:#08x} action={action_flags=:#08x} "
            f"protocol={protocol_flags=:#08x}]"
        )

        def get_proto_flagname(flag: int) -> str | None:
            try:
                return definitions.ProtocolFlagsDisableCallback(flag).name
            except ValueError:
                try:
                    return definitions.ProtocolFlagsOther(flag).name
                except ValueError:
                    return None

        for i in range(32):
            int_value = 2**i
            if all(
                int_value > pf.value for pf in definitions.ProtocolFlagsDisableCallback
            ) and all(int_value > pf.value for pf in definitions.ProtocolFlagsOther):
                break
            self.logger.debug(
                f"{(int_value):#034b} {get_proto_flagname(int_value):<30} "
                f"{bool(protocol_flags & (int_value))!s:8}"
            )

        def get_action_flagname(flag: int) -> str | None:
            try:
                return definitions.ActionFlags(flag).name
            except ValueError:
                return None

        for i in range(32):
            int_value = 2**i
            if all(int_value > af.value for af in definitions.ActionFlags):
                break
            self.logger.debug(
                f"{(int_value):#034b} {get_action_flagname(int_value):<30} "
                f"{bool(action_flags & (int_value))!s:8}"
            )

    def _log_symbols_table(self) -> None:
        for stage, symbols in self.symbols_for_stage.items():
            self.logger.debug(
                f"{stage!r:<32} {', '.join(symbols) if symbols else '<None>'} "
                f"(encoded as {self._encode_symbols_list(stage, symbols)!r})"
            )

    def encode(self) -> Payload:
        protocol_flags, action_flags = self.protocol_flags.encode_to_flags_bitmask()
        if self.logger.getEffectiveLevel() >= logging.DEBUG:
            self._log_flags_table(
                protocol_flags=protocol_flags,
                action_flags=action_flags,
            )
            self._log_symbols_table()

        # Sendmail's libmilter documentation and header files suggests that a list of
        # symbols can be set is using a response with code SMFIR_SETSYMLIST, but that
        # appears to be a lie. Instead, it's appended to the payload of the Options
        # negotiate response.
        symbols_bytes = b"".join(
            [
                self._encode_symbols_list(stage, symbols)
                for stage, symbols in self.symbols_for_stage.items()
            ]
        )
        self.logger.debug(f"{symbols_bytes=}")
        return Payload(
            self.response_char
            + struct.pack("!III", self.protocol_version, action_flags, protocol_flags)
            + symbols_bytes
        )


@attrs.define(auto_attribs=False, kw_only=True)
class Continue(BaseResponseNoData):
    response_char: ClassVar[bytes] = b"c"  # SMFIR_CONTINUE


@attrs.define(auto_attribs=False, kw_only=True)
class Accept(BaseVerdictNoData):
    response_char: ClassVar[bytes] = b"a"  # SMFIR_ACCEPT


@attrs.define(auto_attribs=False, kw_only=True)
class Reject(BaseVerdictNoData):
    response_char: ClassVar[bytes] = b"r"  # SMFIR_REJECT


@attrs.define(auto_attribs=False, kw_only=True)
class BaseReplyWithCode(AbstractVerdict):
    response_char: ClassVar[bytes] = b"y"  # SMFIR_REPLYCODE

    primary_code: tuple[Literal[4, 5], int, int] = attrs.field()
    enhanced_code: tuple[Literal[4, 5], int, int] | None = attrs.field(default=None)
    text: str | None = attrs.field(default=None)

    def encode(self) -> Payload:
        p1, p2, p3 = self.primary_code
        bin_parts_args = [self.response_char + f"{p1}{p2}{p3}".encode()]
        if self.enhanced_code:
            e1, e2, e3 = self.enhanced_code
            bin_parts_args.append(f"{e1}.{e2}.{e3}".encode())
        if self.text:
            bin_parts_args.append(self.text.encode())
        return Payload(b" ".join(bin_parts_args) + b"\x00")


@attrs.define(auto_attribs=False, kw_only=True)
class RejectWithCode(BaseReplyWithCode):
    primary_code: tuple[Literal[5], int, int] = attrs.field()


@attrs.define(auto_attribs=False, kw_only=True)
class TempFailWithCode(BaseReplyWithCode):
    primary_code: tuple[Literal[4], int, int] = attrs.field()


@attrs.define(auto_attribs=False, kw_only=True)
class DiscardMessage(BaseVerdictNoData):
    """
    Drop the message silently, while pretending to accept it for the sender.

    Invalid with Connect or HELO.
    """

    response_char: ClassVar[bytes] = b"d"  # SMFIR_DISCARD


@attrs.define(auto_attribs=False, kw_only=True)
class Quarantine(AbstractVerdict):
    """
    Put the message in the hold queue. Only valid at End of Message stage.
    The reason text is ignored by Postfix at the time of writing.
    https://github.com/vdukhovni/postfix/blob/fe4e81b23b3ee76c64de73d7cb250882fbaaacb9/postfix/src/milter/milter8.c#L1336
    """

    response_char: ClassVar[bytes] = b"q"  # SMFIR_QUARANTINE
    reason: str


@attrs.define(auto_attribs=False, kw_only=True)
class CauseConnectionFail(BaseVerdictNoData):
    """
    Cause an SMTP-connection failure.
    """

    response_char: ClassVar[bytes] = b"f"  # SMFIR_CONN_FAIL


@attrs.define(auto_attribs=False, kw_only=True)
class BaseChangeRecipient(AbstractManipulation):
    recipient: str = attrs.field()

    def encode(self) -> Payload:
        return Payload(self.response_char + self.recipient.encode() + b"\x00")


@attrs.define(auto_attribs=False, kw_only=True)
class AddRecipient(BaseChangeRecipient):
    """
    Add a recipient (RCPT TO) to the message.

    Note that this does not adjust 'To' header (the displayed recipients in user
    agents).
    """

    response_char: ClassVar[bytes] = b"+"  # SMFIR_ADDRCPT


@attrs.define(auto_attribs=False, kw_only=True)
class AddRecipientWithEsmtpArgs(BaseChangeRecipient):
    response_char: ClassVar[bytes] = b"2"  # SMFIR_ADDRCPT_PAR
    esmtp_args: models.EsmtpArgsType = attrs.field()

    def encode(self) -> Payload:
        esmtp_args_str = " ".join(
            f"{key}" if value is None else f"{key}={value}"
            for key, value in self.esmtp_args.items()
        )
        return Payload(
            self.response_char
            + self.recipient.encode()
            + b"\x00"
            + esmtp_args_str.encode()
            + b"\x00"
        )


@attrs.define(auto_attribs=False, kw_only=True)
class RemoveRecipient(BaseChangeRecipient):
    """
    Remove a recipient (RCPT TO) in the message.

    Note that this does not adjust 'To' header (the displayed recipients in user
    agents).
    """

    response_char: ClassVar[bytes] = b"-"  # SMFIR_DELRCPT


@attrs.define(auto_attribs=False, kw_only=True)
class ReplaceBodyChunk(AbstractManipulation):
    """
    Replace the body of the message (by chunk).

    This response has to be called for each split in case the body does not fit in a
    single chunk.
    """

    response_char: ClassVar[bytes] = b"b"  # SMFIR_REPLBODY
    chunk: bytes = attrs.field(
        validator=attrs.validators.max_len(definitions.MAX_DATA_SIZE - 1)
    )

    def encode(self) -> Payload:
        return Payload(self.response_char + self.chunk)


@attrs.define(auto_attribs=False, kw_only=True)
class ChangeMailFrom(AbstractManipulation):
    """
    Replace the envelope-sender (Return-Path) of the message.

    Note that this does not adjust 'From' header (the displayed sender address in user
    agents).

    Note that oddly enough, the Milter protocol has a separate command for adding
    recipients with and without ESMTP arguments, but for changing envelope-from it uses
    a single command.
    """

    response_char: ClassVar[bytes] = b"e"  # SMFIR_CHGFROM
    mail_from: str = attrs.field()
    esmtp_args: models.EsmtpArgsType = attrs.field(factory=dict)

    def encode(self) -> Payload:
        if self.esmtp_args:
            esmtp_args_str = " ".join(
                f"{key}" if value is None else f"{key}={value}"
                for key, value in self.esmtp_args.items()
            )
            return Payload(
                self.response_char
                + self.mail_from.encode()
                + b"\x00"
                + esmtp_args_str.encode()
                + b"\x00"
            )
        return Payload(self.response_char + self.mail_from.encode() + b"\x00")


def validate_headername_rfc5322(headername: str) -> None:
    if not headername:
        raise ValueError("Header field name cannot be empty.")
    if not headername.isascii() or not headername.isprintable() or " " in headername:
        raise ValueError(
            "Header field names must contain only US-ASCII printable characters "
            "with values between 33 and 126 (RFC5322)"
        )
    if ":" in headername:
        raise ValueError("Header field names must not contain a colon (RFC5322)")


@attrs.define(auto_attribs=False, kw_only=True)
class BaseHeaderManipulation(AbstractManipulation):
    headername: str = attrs.field()
    headertext: str = attrs.field()

    @headername.validator  # pyright: ignore [reportGeneralTypeIssues, reportUntypedFunctionDecorator, reportUnknownMemberType]  # noqa: E501
    def check_headername(
        self, attribute: attrs.Attribute[BaseHeaderManipulation], value: str
    ) -> None:
        return validate_headername_rfc5322(value)

    def _encode(self, *, index: int | None = None) -> Payload:
        index_bytes = struct.pack("!I", index) if index is not None else b""
        return Payload(
            self.response_char
            + index_bytes
            + self.headername.encode()
            + b"\x00"
            + self.headertext.encode()
            + b"\x00"
        )


@attrs.define(auto_attribs=False, kw_only=True)
class AppendHeader(BaseHeaderManipulation):
    """
    Append a header.
    """

    response_char: ClassVar[bytes] = b"h"  # SMFIR_ADDHEADER

    def encode(self) -> Payload:
        return self._encode(index=None)


@attrs.define(auto_attribs=False, kw_only=True)
class InsertHeader(BaseHeaderManipulation):
    """
    Add a header at a given position. If you don't care about the position or you don't
    need to deal with having multiple headers with the same name, use AppendHeader
    instead.
    """

    response_char: ClassVar[bytes] = b"i"  # SMFIR_INSHEADER
    index: int = attrs.field()

    @index.validator  # pyright: ignore [reportGeneralTypeIssues, reportUntypedFunctionDecorator, reportUnknownMemberType]  # noqa: E501
    def check_index(self, attribute: attrs.Attribute[InsertHeader], value: int) -> None:
        if bool(value < 0):
            raise ValueError("Header index must be positive.")

    def encode(self) -> Payload:
        return self._encode(index=self.index)


@attrs.define(auto_attribs=False, kw_only=True)
class ChangeHeader(BaseHeaderManipulation):
    """
    Replace the header by the provided headername. If mulitple are present, indicate the
    occurence by its index within the set with the name.

    Provide an empty headertext to delete the header.
    """

    response_char: ClassVar[bytes] = b"m"  # SMFIR_CHGHEADER
    nth_occurrence: int = attrs.field(default=0)

    @nth_occurrence.validator  # pyright: ignore [reportGeneralTypeIssues, reportUntypedFunctionDecorator, reportUnknownMemberType]  # noqa: E501
    def check_nth_occurrence(
        self, attribute: attrs.Attribute[ChangeHeader], value: int
    ) -> None:
        if bool(value < 0):
            raise ValueError("Header index (nth_occurrence) must be positive.")

    def encode(self) -> Payload:
        return self._encode(index=self.nth_occurrence)


@attrs.define(auto_attribs=False, kw_only=True)
class SkipToNextStage(BaseResponseNoData):
    """
    On Postfix, this means skipping any further events of the same type; e.g. returning
    this during an Rcpt To hook, the MTA skips over subsequent Rcpt To calls, so the
    next one is likely to be Data.

    Useful in case this involves many calls and bandwidth/latency, to indicate enough
    information has been received to make a decision (in a next stage!).

    On Sendmail this is only valid as a response to the Body chunk commands to skip
    further chunks and move to the End of message stage.
    """

    response_char: ClassVar[bytes] = b"s"  # SMFIR_SKIP


@attrs.define(auto_attribs=False, kw_only=True)
class Progress(BaseResponseNoData):
    """
    Inform the MTA that the Milter is still processing and that it's still alive (resets
    connection timeout).

    TODO: adjust the API to allow for sending this response multiple times before
          sending a verdict response.
    """

    response_char: ClassVar[bytes] = b"p"  # SMFIR_PROGRESS


VerdictOrContinue: TypeAlias = AbstractVerdict | Continue
