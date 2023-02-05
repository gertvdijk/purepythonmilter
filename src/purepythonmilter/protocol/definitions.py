# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import enum
from typing import Final

"""
Low-level Milter protocol definitions.
Comments refer to Sendmail's libmilter source code header file definitions.
"""

VERSION: Final[int] = 6  # SMFI_PROT_VERSION
# length of network byte order 32 bit unsigned integer in bytes
BASE_LEN_BYTES: Final[int] = 4  # MILTER_LEN_BYTES
# Postfix sends packets with payload length 65536 (expected 65535).
MAX_DATA_SIZE: Final[int] = 65536  # MILTER_MAX_DATA_SIZE (+ 1)
PROTOCOL_FLAGS_ALL: Final[int] = 0x001FFFFF  # SMFI_CURR_PROT


@enum.unique
class ActionFlags(enum.Enum):
    ADD_HEADERS = 0x00000001  # SMFIF_ADDHDRS
    CHANGE_BODY = 0x00000002  # SMFIF_CHGBODY
    ADD_RECIPIENTS = 0x00000004  # SMFIF_ADDRCPT
    ADD_RECIPIENT_ESMTP_ARGS = 0x00000080  # SMFIF_ADDRCPT_PAR
    REMOVE_RECIPIENTS = 0x00000008  # SMFIF_DELRCPT
    CHANGE_HEADERS = 0x00000010  # SMFIF_CHGHDRS
    QUARANTINE = 0x00000020  # SMFIF_QUARANTINE
    CHANGE_ENVELOPE_FROM = 0x00000040  # SMFIF_CHGFROM
    SET_MACROS_LIST = 0x00000100  # SMFIF_SETSYMLIST


@enum.unique
class ProtocolFlagsDisableCallback(enum.Enum):
    # Skips callback Command.CONNECTION_INFO.
    CONNECT = 0x00000001  # SMFIP_NOCONNECT
    # Skips callback Command.HELO.
    HELO = 0x00000002  # SMFIP_NOHELO
    # Skips callback Command.MAIL_FROM.
    MAIL_FROM = 0x00000004  # SMFIP_NOMAIL
    # Skips callback Command.RCPT_TO.
    RCPT_TO = 0x00000008  # SMFIP_NORCPT
    # Skips callback Command.BODY_CHUNK.
    BODY = 0x00000010  # SMFIP_NOBODY
    # Skips callback Command.HEADER.
    HEADERS = 0x00000020  # SMFIP_NOHDRS
    # Skips callback Command.END_OF_HEADERS.
    END_OF_HEADERS = 0x00000040  # SMFIP_NOEOH
    # Skips callback Command.UNKNOWN.
    UNKNOWN = 0x00000100  # SMFIP_NOUNKNOWN
    # Skips callback Command.DATA.
    DATA = 0x00000200  # SMFIP_NODATA

    # SMFIP_NR_* flags indicate to the server that this Milter will not send a reply at
    # the given command. When enabled, implies Action.CONTINUE statically, and would
    # save sending that reply over the network.
    REPLY_HEADERS = 0x00000080  # SMFIP_NR_HDR / SMFIP_NOHREPL (sharing value).
    REPLY_CONNECTION = 0x00001000  # SMFIP_NR_CONN
    REPLY_HELO = 0x00002000  # SMFIP_NR_HELO
    REPLY_MAIL_FROM = 0x00004000  # SMFIP_NR_MAIL
    REPLY_RCPT_TO = 0x00008000  # SMFIP_NR_RCPT
    REPLY_DATA = 0x00010000  # SMFIP_NR_DATA
    REPLY_UNKNOWN = 0x00020000  # SMFIP_NR_UNKN
    REPLY_END_OF_HEADERS = 0x00040000  # SMFIP_NR_EOH
    REPLY_BODY_CHUNK = 0x00080000  # SMFIP_NR_BODY


@enum.unique
class ProtocolFlagsOther(enum.Enum):
    # Indicates ability to perform Action.SKIP.
    SKIP = 0x00000400  # SMFIP_SKIP
    # Whether or not to send a callback on recipients that were rejected already.
    SEND_REJECTED_RCPT_TOS = 0x00000800  # SMFIP_RCPT_REJ
    # Whether or not to keep the leading spaces (continuation) in the unfolded header
    # value.
    HEADER_VALUE_LEADING_SPACE = 0x00100000  # SMFIP_HDR_LEADSPC


ProtocolFlagsAllType = ProtocolFlagsDisableCallback | ProtocolFlagsOther


@enum.unique
class MacroStage(enum.Enum):
    # Not all stages are defined in libmilter, but Postfix sends them, yet does not
    # allow them for customization. 🤷
    #   postfix/smtpd[...]: warning: milter [...]: ignoring unknown macro type [...]
    CONNECT = 0  # SMFIM_CONNECT
    HELO = 1  # SMFIM_HELO
    MAIL_FROM = 2  # SMFIM_ENVFROM
    RCPT_TO = 3  # SMFIM_ENVRCPT
    DATA = 4  # SMFIM_DATA
    HEADER = 7
    END_OF_HEADERS = 6  # SMFIM_EOH
    BODY = 8
    END_OF_MESSAGE = 5  # SMFIM_EOM
    UNKNOWN = 9


@enum.unique
class AddressFamily(enum.Enum):
    UNKNOWN = b"U"  # SMFIA_UNKNOWN
    UNIX_SOCKET = b"L"  # SMFIA_UNIX
    IPV4 = b"4"  # SMFIA_INET
    IPV6 = b"6"  # SMFIA_INET6
