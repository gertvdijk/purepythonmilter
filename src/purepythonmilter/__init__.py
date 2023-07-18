# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0
#

from __future__ import annotations

from ._version import __version__
from .api.application import PurePythonMilter
from .api.models import (
    ConnectionInfoArgsIPv4,
    ConnectionInfoArgsIPv6,
    ConnectionInfoArgsUnixSocket,
    ConnectionInfoUnknown,
)
from .protocol.commands import (
    Abort,
    BodyChunk,
    Connect,
    Data,
    EndOfHeaders,
    EndOfMessage,
    Header,
    Helo,
    MailFrom,
    Quit,
    RcptTo,
    Unknown,
)
from .protocol.responses import (
    Accept,
    AddRecipient,
    AddRecipientWithEsmtpArgs,
    AppendHeader,
    CauseConnectionFail,
    ChangeHeader,
    ChangeMailFrom,
    Continue,
    DiscardMessage,
    InsertHeader,
    Progress,
    Quarantine,
    Reject,
    RejectWithCode,
    RemoveRecipient,
    ReplaceBodyChunk,
    SkipToNextStage,
    TempFailWithCode,
    VerdictOrContinue,
)

__all__ = [
    "__version__",
    "Abort",
    "Accept",
    "AddRecipient",
    "AddRecipientWithEsmtpArgs",
    "AppendHeader",
    "BodyChunk",
    "CauseConnectionFail",
    "ChangeHeader",
    "ChangeMailFrom",
    "Connect",
    "ConnectionInfoArgsIPv4",
    "ConnectionInfoArgsIPv6",
    "ConnectionInfoArgsUnixSocket",
    "ConnectionInfoUnknown",
    "Continue",
    "Data",
    "DiscardMessage",
    "EndOfHeaders",
    "EndOfMessage",
    "Header",
    "Helo",
    "InsertHeader",
    "MailFrom",
    "Progress",
    "PurePythonMilter",
    "Quarantine",
    "Quit",
    "RcptTo",
    "Reject",
    "RejectWithCode",
    "RemoveRecipient",
    "ReplaceBodyChunk",
    "SkipToNextStage",
    "TempFailWithCode",
    "Unknown",
    "VerdictOrContinue",
]

DEFAULT_LISTENING_TCP_IP = "127.0.0.1"
DEFAULT_LISTENING_TCP_PORT = 9000
