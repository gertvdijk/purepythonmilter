# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING

import attrs

from purepythonmilter.protocol import definitions

if TYPE_CHECKING:
    import ipaddress


class MilterServerConnectionID(uuid.UUID):
    @property
    def short(self) -> str:
        return self.shorten()

    def shorten(self, length: int = 8) -> str:
        return str(self)[:length]

    @classmethod
    def generate(cls) -> MilterServerConnectionID:
        return MilterServerConnectionID(bytes=uuid.uuid4().bytes)


connection_id_context: ContextVar[MilterServerConnectionID] = ContextVar(
    "connection_id"
)


@attrs.define(kw_only=True)
class RequestProtocolFlags:
    """
    Default values reflect the very minimum / most optimized negotiation.
    Your Milter app won't see much other than End of message callback (mandatory).
    """

    call_connect: bool = False
    call_helo: bool = False
    call_mail_from: bool = False
    call_rcpt_to: bool = False
    call_rcpt_to_rejected: bool = False
    call_data: bool = False
    call_headers: bool = False
    call_end_of_headers: bool = False
    call_body_chunk: bool = False
    call_unknown: bool = False

    reply_connect: bool = False
    reply_helo: bool = False
    reply_mail_from: bool = False
    reply_rcpt_to: bool = False
    reply_data: bool = False
    reply_headers: bool = False
    reply_end_of_headers: bool = False
    reply_body_chunk: bool = False
    reply_unknown: bool = False

    can_change_mail_from: bool = False
    can_add_headers: bool = False
    can_change_headers: bool = False
    can_change_body: bool = False
    can_add_recipients: bool = False
    can_add_recipients_with_esmtp_args: bool = False
    can_remove_recipients: bool = False
    can_quarantine: bool = False
    can_specify_macros: bool = True
    can_skip_body_chunks: bool = True

    headers_with_leading_space: bool = False

    def encode_to_flags_bitmask(  # noqa: PLR0912, PLR0915, C901
        self,
    ) -> tuple[int, int]:
        protocol_flags, action_flags = 0, 0
        if not self.call_connect:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.CONNECT.value
        if not self.call_helo:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.HELO.value
        if not self.call_mail_from:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.MAIL_FROM.value
        if not self.call_rcpt_to:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.RCPT_TO.value
        if self.call_rcpt_to_rejected:
            protocol_flags |= (
                definitions.ProtocolFlagsOther.SEND_REJECTED_RCPT_TOS.value
            )
        if not self.call_data:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.DATA.value
        if not self.call_headers:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.HEADERS.value
        if not self.call_end_of_headers:
            protocol_flags |= (
                definitions.ProtocolFlagsDisableCallback.END_OF_HEADERS.value
            )
        if not self.call_body_chunk:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.BODY.value
        if not self.call_unknown:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.UNKNOWN.value

        if not self.reply_connect:
            protocol_flags |= (
                definitions.ProtocolFlagsDisableCallback.REPLY_CONNECTION.value
            )
        if not self.reply_helo:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.REPLY_HELO.value
        if not self.reply_mail_from:
            protocol_flags |= (
                definitions.ProtocolFlagsDisableCallback.REPLY_MAIL_FROM.value
            )
        if not self.reply_rcpt_to:
            protocol_flags |= (
                definitions.ProtocolFlagsDisableCallback.REPLY_RCPT_TO.value
            )
        if not self.reply_data:
            protocol_flags |= definitions.ProtocolFlagsDisableCallback.REPLY_DATA.value
        if not self.reply_headers:
            protocol_flags |= (
                definitions.ProtocolFlagsDisableCallback.REPLY_HEADERS.value
            )
        if not self.reply_end_of_headers:
            protocol_flags |= (
                definitions.ProtocolFlagsDisableCallback.REPLY_END_OF_HEADERS.value
            )
        if not self.reply_body_chunk:
            protocol_flags |= (
                definitions.ProtocolFlagsDisableCallback.REPLY_BODY_CHUNK.value
            )
        if not self.reply_unknown:
            protocol_flags |= (
                definitions.ProtocolFlagsDisableCallback.REPLY_UNKNOWN.value
            )

        if self.can_change_mail_from:
            action_flags |= definitions.ActionFlags.CHANGE_ENVELOPE_FROM.value
        if self.can_add_headers:
            action_flags |= definitions.ActionFlags.ADD_HEADERS.value
        if self.can_change_headers:
            action_flags |= definitions.ActionFlags.CHANGE_HEADERS.value
        if self.can_change_body:
            action_flags |= definitions.ActionFlags.CHANGE_BODY.value
        if self.can_add_recipients:
            action_flags |= definitions.ActionFlags.ADD_RECIPIENTS.value
        if self.can_add_recipients_with_esmtp_args:
            action_flags |= definitions.ActionFlags.ADD_RECIPIENT_ESMTP_ARGS.value
        if self.can_remove_recipients:
            action_flags |= definitions.ActionFlags.REMOVE_RECIPIENTS.value
        if self.can_quarantine:
            action_flags |= definitions.ActionFlags.QUARANTINE.value
        if self.can_specify_macros:
            action_flags |= definitions.ActionFlags.SET_MACROS_LIST.value
        if self.can_skip_body_chunks:
            protocol_flags |= definitions.ProtocolFlagsOther.SKIP.value

        if self.headers_with_leading_space:
            protocol_flags |= (
                definitions.ProtocolFlagsOther.HEADER_VALUE_LEADING_SPACE.value
            )

        return protocol_flags, action_flags


@attrs.define(kw_only=True)
class MtaSupportsProtocolFlags:
    disable_call_connect: bool
    disable_call_helo: bool
    disable_call_mail_from: bool
    disable_call_rcpt_to: bool
    disable_call_rcpt_to_rejected: bool
    disable_call_data: bool
    disable_call_headers: bool
    disable_call_end_of_headers: bool
    disable_call_body_chunk: bool
    disable_call_unknown: bool

    disable_reply_connect: bool
    disable_reply_helo: bool
    disable_reply_mail_from: bool
    disable_reply_rcpt_to: bool
    disable_reply_data: bool
    disable_reply_headers: bool
    disable_reply_end_of_headers: bool
    disable_reply_body_chunk: bool
    disable_reply_unknown: bool

    allows_change_mail_from: bool
    allows_add_headers: bool
    allows_change_headers: bool
    allows_change_body: bool
    allows_add_recipients: bool
    allows_add_recipients_with_esmtp_args: bool
    allows_remove_recipients: bool
    allows_quarantine: bool
    allows_specify_macros: bool
    allows_skip_body_chunks: bool

    headers_with_leading_space: bool

    @classmethod
    def from_binary_flags(
        cls, *, protocol_flags: int, action_flags: int
    ) -> MtaSupportsProtocolFlags:
        return MtaSupportsProtocolFlags(
            disable_call_connect=bool(
                protocol_flags & definitions.ProtocolFlagsDisableCallback.CONNECT.value
            ),
            disable_call_helo=bool(
                protocol_flags & definitions.ProtocolFlagsDisableCallback.HELO.value
            ),
            disable_call_mail_from=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.MAIL_FROM.value
            ),
            disable_call_rcpt_to=bool(
                protocol_flags & definitions.ProtocolFlagsDisableCallback.RCPT_TO.value
            ),
            disable_call_rcpt_to_rejected=bool(
                protocol_flags
                & definitions.ProtocolFlagsOther.SEND_REJECTED_RCPT_TOS.value
            ),
            disable_call_data=bool(
                protocol_flags & definitions.ProtocolFlagsDisableCallback.DATA.value
            ),
            disable_call_headers=bool(
                protocol_flags & definitions.ProtocolFlagsDisableCallback.HEADERS.value
            ),
            disable_call_end_of_headers=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.END_OF_HEADERS.value
            ),
            disable_call_body_chunk=bool(
                protocol_flags & definitions.ProtocolFlagsDisableCallback.BODY.value
            ),
            disable_call_unknown=bool(
                protocol_flags & definitions.ProtocolFlagsDisableCallback.UNKNOWN.value
            ),
            disable_reply_connect=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_CONNECTION.value
            ),
            disable_reply_helo=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_HELO.value
            ),
            disable_reply_mail_from=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_MAIL_FROM.value
            ),
            disable_reply_rcpt_to=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_RCPT_TO.value
            ),
            disable_reply_data=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_DATA.value
            ),
            disable_reply_headers=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_HEADERS.value
            ),
            disable_reply_end_of_headers=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_END_OF_HEADERS.value
            ),
            disable_reply_body_chunk=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_BODY_CHUNK.value
            ),
            disable_reply_unknown=bool(
                protocol_flags
                & definitions.ProtocolFlagsDisableCallback.REPLY_UNKNOWN.value
            ),
            allows_change_mail_from=bool(
                action_flags & definitions.ActionFlags.CHANGE_ENVELOPE_FROM.value
            ),
            allows_add_headers=bool(
                action_flags & definitions.ActionFlags.ADD_HEADERS.value
            ),
            allows_change_headers=bool(
                action_flags & definitions.ActionFlags.CHANGE_HEADERS.value
            ),
            allows_change_body=bool(
                action_flags & definitions.ActionFlags.CHANGE_BODY.value
            ),
            allows_add_recipients=bool(
                action_flags & definitions.ActionFlags.ADD_RECIPIENTS.value
            ),
            allows_add_recipients_with_esmtp_args=bool(
                action_flags & definitions.ActionFlags.ADD_RECIPIENT_ESMTP_ARGS.value
            ),
            allows_remove_recipients=bool(
                action_flags & definitions.ActionFlags.REMOVE_RECIPIENTS.value
            ),
            allows_quarantine=bool(
                action_flags & definitions.ActionFlags.QUARANTINE.value
            ),
            allows_specify_macros=bool(
                action_flags & definitions.ActionFlags.SET_MACROS_LIST.value
            ),
            allows_skip_body_chunks=bool(
                protocol_flags & definitions.ProtocolFlagsOther.SKIP.value
            ),
            headers_with_leading_space=bool(
                protocol_flags
                & definitions.ProtocolFlagsOther.HEADER_VALUE_LEADING_SPACE.value
            ),
        )


class ConnectionInfoArgs:
    ...


@attrs.define(kw_only=True, slots=True, frozen=True)
class ConnectionInfoArgsUnixSocket(ConnectionInfoArgs):
    path: str


@attrs.define(kw_only=True, slots=True, frozen=True)
class ConnectionInfoArgsIPv4(ConnectionInfoArgs):
    hostname: str
    addr: ipaddress.IPv4Address
    port: int


@attrs.define(kw_only=True, slots=True, frozen=True)
class ConnectionInfoArgsIPv6(ConnectionInfoArgs):
    hostname: str
    addr: ipaddress.IPv6Address
    port: int


@attrs.define(kw_only=True, slots=True, frozen=True)
class ConnectionInfoUnknown(ConnectionInfoArgs):
    description: str


EsmtpArgsType = dict[str, str | None]
