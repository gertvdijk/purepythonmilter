# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import abc
import ipaddress
import logging
import struct
from collections.abc import Mapping
from typing import Any, ClassVar, Literal, TypeAlias

import attrs

from ..api import logger, models
from . import definitions
from .exceptions import ProtocolViolationCommandData

CommandDataRaw: TypeAlias = bytes

# Filled by BaseCommand.__init_subclass__()
chars_to_command_registry: dict[bytes, type[BaseCommand]] = {}


_logger = logging.getLogger(__name__)


def _decode_array(data: bytes) -> list[bytes]:
    if not data:
        return []
    return data.removesuffix(b"\x00").split(b"\x00")


# slots=False for any subclass of this, because attrs doesn't play nice with
# __init_subclass__ when enabled.
@attrs.define(auto_attribs=False)
class BaseCommand(abc.ABC):
    command_char: ClassVar[bytes]
    logger: logging.LoggerAdapter[logging.Logger] = attrs.field(
        init=False, eq=False, repr=False
    )
    # Attribute 'data_raw' is here to handle any (invalid) data even for commands that
    # should not have any and the PacketDecoder does not have to guard about that.
    data_raw: CommandDataRaw = attrs.field(default=None)

    def __attrs_post_init__(self) -> None:
        self.logger = logger.ConnectionContextLogger().get(__name__)
        if self.data_raw is not None and self.data_raw != b"":
            raise ProtocolViolationCommandData(
                f"Expected no data for command {self.__class__.__name__}"
            )

    def __str__(self) -> str:
        return f"{self.__class__.__name__} command [nodata]"

    def __init_subclass__(cls, *args: Any, **kwargs: Any) -> None:
        super().__init_subclass__(*args, **kwargs)
        if hasattr(cls, "command_char"):
            if cmd := chars_to_command_registry.get(cls.command_char):
                raise ValueError(
                    f"Command registration for {cls=!r} failed; command char "
                    f"{cls.command_char!r} is already registered to {cmd=!r}."
                )
            if len(cls.command_char) != 1:
                raise ValueError(
                    f"Command registration for {cls=!r} failed; command char "
                    f"must be exactly one byte."
                )
            _logger.debug(f"registered {cls.command_char!r} to {cmd}")
            chars_to_command_registry[cls.command_char] = cls


@attrs.define(auto_attribs=False, slots=False)
class BaseCommandWithData(BaseCommand):
    data_raw: CommandDataRaw = attrs.field()

    def __attrs_post_init__(self) -> None:
        self.logger = logger.ConnectionContextLogger().get(__name__)
        self._decode()

    @abc.abstractmethod
    def _decode(self) -> None:
        ...  # pragma: nocover

    def __str__(self) -> str:
        return f"{self.__class__.__name__} command [data=<{len(self.data_raw)} bytes>]"


@attrs.define(auto_attribs=False, slots=False)
class OptionsNegotiate(BaseCommandWithData):
    command_char: ClassVar[bytes] = b"O"  # SMFIC_OPTNEG
    flags: models.MtaSupportsProtocolFlags = attrs.field(init=False)

    def _decode(self) -> None:
        self.logger.debug(f"decoding options negotiate {self.data_raw.hex()=}")
        expected_data_length = definitions.BASE_LEN_BYTES * 3  # MILTER_OPTLEN
        if len(self.data_raw) != expected_data_length:
            raise ProtocolViolationCommandData(
                "Length of options negotiate request data is not valid. Got "
                f"{len(self.data_raw)}, expected {expected_data_length}."
            )
        milter_protocol_version, action_flags, protocol_flags = struct.unpack(
            "!III", self.data_raw
        )
        self.logger.debug(
            f"MTA: {milter_protocol_version=:#08x} {action_flags=:#08x} "
            f"{protocol_flags=:#08x}"
        )
        if milter_protocol_version != definitions.VERSION:
            raise ProtocolViolationCommandData(
                f"Unexpected Milter protocol version. Got "
                f"{milter_protocol_version}, expected {definitions.VERSION}"
            )
        if protocol_flags != definitions.PROTOCOL_FLAGS_ALL:
            self.logger.warning(
                "This MTA connection does not support all protocol flags. Are "
                "you using a modern Postfix? Milter may misbehave. "
                f"[{protocol_flags=:#08x}]",
            )

        self.flags = models.MtaSupportsProtocolFlags.from_binary_flags(
            protocol_flags=protocol_flags, action_flags=action_flags
        )
        self.logger.debug(f"{self.flags=}")


@attrs.define(auto_attribs=False, slots=False)
class Connect(BaseCommandWithData):
    command_char: ClassVar[bytes] = b"C"  # SMFIC_CONNECT
    connection_info_args: models.ConnectionInfoArgs = attrs.field(init=False)
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)

    def _decode(self) -> None:
        self.connection_info_args = self._decode_connection_info()

    def _decode_connection_info(self) -> models.ConnectionInfoArgs:
        # Example data:
        #   b'[172.17.0.1]\x004\xc36172.17.0.1\x00'
        #   b'ignored_hostname\x00L\x00\x00/run/mysock\x00'
        items = self.data_raw.split(b"\x00", maxsplit=1)
        if len(items) != 2:
            raise ProtocolViolationCommandData(
                "Connection info data does not contain expected number of NULLs to "
                "split into hostname, socket family and host address."
            )
        hostname_bin, socket_data = items
        try:
            hostname = hostname_bin.decode("utf-8")
        except ValueError as e:
            raise ProtocolViolationCommandData(
                f"Could not decode hostname in socket data {hostname_bin=!r}"
            ) from e
        family, hostaddr_port, hostaddr_str = self._decode_socket_tuple(
            socket_data.rstrip(b"\x00")
        )

        self.logger.debug(
            f"_decode_connection_info {hostname=} "
            f"family={family.name} {hostaddr_port=} {hostaddr_str=}"
        )
        # We could do a nice pattern matching here extracting the tuple etc, but mypy
        # fails: https://github.com/python/mypy/issues/12533#issuecomment-1162496540
        match family:
            case definitions.AddressFamily.IPV4:
                try:
                    addr = ipaddress.IPv4Address(hostaddr_str)
                except ipaddress.AddressValueError:
                    raise ProtocolViolationCommandData(
                        f"Unsupported socket data hostaddr value {hostaddr_str!r} for "
                        f"family={family.name}"
                    )
                assert isinstance(hostaddr_port, int)  # Have to help mypy here? 😕
                return models.ConnectionInfoArgsIPv4(
                    hostname=hostname, addr=addr, port=hostaddr_port
                )
            case definitions.AddressFamily.IPV6:
                try:
                    addr6 = ipaddress.IPv6Address(hostaddr_str)
                except ipaddress.AddressValueError:
                    raise ProtocolViolationCommandData(
                        f"Unsupported socket data hostaddr value {hostaddr_str!r} for "
                        f"family={family.name}"
                    )
                assert isinstance(hostaddr_port, int)  # Have to help mypy here? 😕
                return models.ConnectionInfoArgsIPv6(
                    hostname=hostname, addr=addr6, port=hostaddr_port
                )
            case definitions.AddressFamily.UNIX_SOCKET:
                assert isinstance(hostaddr_str, str)  # Have to help mypy here? 😕
                return models.ConnectionInfoArgsUnixSocket(path=hostaddr_str)
            case definitions.AddressFamily.UNKNOWN:
                # This can happen when Postfix is unable to obtain the client IP from
                # the kernel for whatever is the reason. Shows up like
                #   postfix/smtpd[...]: connect from unknown[unknown]
                # in Postfix smtpd logs.
                return models.ConnectionInfoUnknown(description=hostname)

    def _decode_socket_tuple(
        self, socket_data: bytes
    ) -> (
        tuple[
            Literal[definitions.AddressFamily.IPV4, definitions.AddressFamily.IPV6],
            int,
            str,
        ]
        | tuple[Literal[definitions.AddressFamily.UNIX_SOCKET], None, str]
        | tuple[Literal[definitions.AddressFamily.UNKNOWN], None, None]
    ):
        # Example data:
        #   b'4\xc36172.17.0.1'
        if not socket_data:
            raise ProtocolViolationCommandData("Socket data empty")
        family_bin: int = struct.unpack("c", socket_data[0:1])[0]
        self.logger.debug(f"Decoded socket data {family_bin=!r}")
        try:
            family = definitions.AddressFamily(family_bin)
        except ValueError:
            raise ProtocolViolationCommandData(
                f"Unsupported socket family {family_bin!r} in connection socket info."
            )

        match family:
            case definitions.AddressFamily.IPV4 | definitions.AddressFamily.IPV6:
                if not len(socket_data) >= 6:
                    raise ProtocolViolationCommandData(
                        "Socket data should contain more than six bytes for IPv4/IPv6."
                    )
                port: int = struct.unpack("!H", socket_data[1:3])[0]
                try:
                    address = socket_data[3:].decode("ascii")
                except ValueError as e:
                    raise ProtocolViolationCommandData(
                        f"Could not decode IP address in socket data {socket_data=!r}"
                    ) from e
                else:
                    return family, port, address
            case definitions.AddressFamily.UNIX_SOCKET:
                try:
                    socketpath = socket_data[3:].decode("utf-8")
                except ValueError as e:
                    raise ProtocolViolationCommandData(
                        f"Could not decode socket path in socket data {socket_data=!r}"
                    ) from e
                else:
                    return family, None, socketpath
            case definitions.AddressFamily.UNKNOWN:
                return family, None, None


@attrs.define(auto_attribs=False, slots=False)
class Helo(BaseCommandWithData):
    command_char: ClassVar[bytes] = b"H"  # SMFIC_HELO
    hostname: str = attrs.field(init=False)
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)

    def _decode(self) -> None:
        if not self.data_raw or self.data_raw[-1:] != b"\x00":
            raise ProtocolViolationCommandData(
                f"Helo hostname should be NULL-terminated. [data={self.data_raw!r}]"
            )
        # HELO/EHLO data can't be UTF-8, because it's this very stage in which SMTPUTF8
        # awareness is negotiated.
        # https://datatracker.ietf.org/doc/html/rfc6531#section-3.7.1
        self.hostname = self.data_raw.rstrip(b"\x00").decode(
            "ascii", "backslashreplace"
        )


@attrs.define(auto_attribs=False, slots=False)
class BaseMailFromAndRcptTo(BaseCommandWithData):
    """
    Given the data for a 'MAIL FROM' or 'RCPT TO' command, decode to an address and the
    ESMTP parameters. A value is optional, which results in a None value in the
    esmtp_args dict. E.g. with input:
        b'<test@example.com>\x00BODY=8BITMIME\x00FOO\x00'
    this should be decoded to:
        address='<test@example.com>'
        esmtp_args={'BODY': '8BITMIME', 'FOO': None}
    """

    address: str = attrs.field(init=False)
    esmtp_args: models.EsmtpArgsType = attrs.field(init=False, factory=dict)
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)

    def _decode(self) -> None:
        data = self.data_raw
        if not data or data[-1:] != b"\x00":
            raise ProtocolViolationCommandData(
                f"Mail From / Rcpt To address should be NULL-terminated. [{data=!r}]"
            )
        data_stripped = data.rstrip(b"\x00")
        if not data_stripped:
            raise ProtocolViolationCommandData(
                f"Mail From / Rcpt To address seems empty. [{data=!r}]"
            )
        address_data, esmtp_args_data = data.split(b"\x00", maxsplit=1)
        address = address_data.decode("utf-8", "backslashreplace")

        if not address.startswith("<") or not address.endswith(">"):
            self.logger.warning(
                f"Address in Mail From / Rcpt To {address!r} appears not enclosed in "
                "angle brackets."
            )
            self.address = address
        else:
            self.address = address[1:-1]

        if not esmtp_args_data:
            return

        esmtp_args_items = _decode_array(esmtp_args_data)
        self.esmtp_args: models.EsmtpArgsType = {}
        for esmtp_data_item_raw in esmtp_args_items:
            if b"=" not in esmtp_data_item_raw[1:]:
                # keyword-only case.
                keyword_raw, value_raw = esmtp_data_item_raw, None
            else:
                try:
                    keyword_raw, value_raw = esmtp_data_item_raw.split(b"=")
                except ValueError as e:
                    raise ProtocolViolationCommandData(
                        "Could not decode ESMTP keyword/value pair in "
                        f"{esmtp_data_item_raw=!r}"
                    ) from e
            # Note that esmtp-keyword is not UTF-8 with SMTPUTF8 extension, only the
            # esmtp-value is.
            # https://datatracker.ietf.org/doc/html/rfc6531#section-3.3
            try:
                keyword = keyword_raw.decode("ascii")
            except ValueError as e:
                raise ProtocolViolationCommandData(
                    f"Could not decode ESMTP keyword {keyword_raw=!r}"
                ) from e

            if value_raw is not None:
                value = value_raw.decode("utf-8", "backslashreplace")
            else:
                value = None

            if (
                former_value := self.esmtp_args.get(keyword)
            ) is not None and value != former_value:
                self.logger.debug(
                    "ESMTP keyword already seen for this command, overriding former "
                    f"value {keyword=} {former_value=} {value=}",
                )
            self.esmtp_args[keyword] = value


class MailFrom(BaseMailFromAndRcptTo):
    command_char: ClassVar[bytes] = b"M"  # SMFIC_MAIL


class RcptTo(BaseMailFromAndRcptTo):
    """Called on each recipient individually."""

    command_char: ClassVar[bytes] = b"R"  # SMFIC_RCPT


@attrs.define(auto_attribs=False, slots=False)
class Data(BaseCommand):
    command_char: ClassVar[bytes] = b"T"  # SMFIC_DATA
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)


@attrs.define(auto_attribs=False, slots=False)
class Header(BaseCommandWithData):
    """Called on each header individually."""

    command_char: ClassVar[bytes] = b"L"  # SMFIC_HEADER
    name: str = attrs.field(init=False)
    text: str = attrs.field(init=False)
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)

    def _decode(self) -> None:
        # Example data:
        #   b'From\x00Display Name <user@example.com>\x00'
        if not self.data_raw or self.data_raw[-1:] != b"\x00":
            raise ProtocolViolationCommandData(
                f"Header data should be NULL-terminated. [data={self.data_raw!r}]"
            )
        items = _decode_array(self.data_raw)
        if len(items) != 2:
            raise ProtocolViolationCommandData(
                f"Could not decode the header data={self.data_raw!r}"
            )
        name_raw, value_raw = items
        self.name, self.text = name_raw.decode(
            "ascii", "backslashreplace"
        ), value_raw.decode("utf-8", "backslashreplace")


@attrs.define(auto_attribs=False, slots=False)
class EndOfHeaders(BaseCommand):
    command_char: ClassVar[bytes] = b"N"  # SMFIC_EOH
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)


@attrs.define(auto_attribs=False, slots=False)
class BodyChunk(BaseCommandWithData):
    command_char: ClassVar[bytes] = b"B"  # SMFIC_BODY
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)

    def _decode(self) -> None:
        pass


@attrs.define(auto_attribs=False, slots=False)
class EndOfMessage(BaseCommand):
    command_char: ClassVar[bytes] = b"E"  # SMFIC_BODYEOB
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)


@attrs.define(auto_attribs=False, slots=False)
class Abort(BaseCommand):
    command_char: ClassVar[bytes] = b"A"  # SMFIC_ABORT


@attrs.define(auto_attribs=False, slots=False)
class Quit(BaseCommand):
    command_char: ClassVar[bytes] = b"Q"  # SMFIC_QUIT


@attrs.define(auto_attribs=False, slots=False)
class QuitNoClose(BaseCommand):
    """Like Quit, but new connection follows."""

    command_char: ClassVar[bytes] = b"K"  # SMFIC_QUIT_NC


@attrs.define(auto_attribs=False, slots=False)
class Unknown(BaseCommandWithData):
    """
    Unrecognized or unimplemented SMTP command. As this is completely unspecified; the
    'data_raw' attribute contains the raw value passed from the MTA with the
    NULL-termination removed.

    Example: b"HELP\x00"
    Decodes to: b"HELP"
    """

    command_char: ClassVar[bytes] = b"U"  # SMFIC_UNKNOWN
    macros: Mapping[str, str] = attrs.field(init=False, factory=dict)

    def _decode(self) -> None:
        self.data_raw = self.data_raw.removesuffix(b"\x00")


@attrs.define(auto_attribs=False, slots=False)
class DefineMacro(BaseCommandWithData):
    command_char: ClassVar[bytes] = b"D"  # SMFIC_MACRO
    stage: definitions.MacroStage = attrs.field(init=False)
    macros: dict[str, str] = attrs.field(factory=dict[str, str], init=False)
    command_char_to_stage: ClassVar[Mapping[bytes, definitions.MacroStage]] = {
        Connect.command_char: definitions.MacroStage.CONNECT,
        Helo.command_char: definitions.MacroStage.HELO,
        MailFrom.command_char: definitions.MacroStage.MAIL_FROM,
        RcptTo.command_char: definitions.MacroStage.RCPT_TO,
        Data.command_char: definitions.MacroStage.DATA,
        Header.command_char: definitions.MacroStage.HEADER,
        EndOfHeaders.command_char: definitions.MacroStage.END_OF_HEADERS,
        BodyChunk.command_char: definitions.MacroStage.BODY,
        EndOfMessage.command_char: definitions.MacroStage.END_OF_MESSAGE,
        Unknown.command_char: definitions.MacroStage.UNKNOWN,
    }

    def _decode(self) -> None:
        # Example data:
        #   b'Cj\x00myhost.sub.example.com\x00{daemon_addr}\x00172.17.0.2\x00'
        # Should decode to:
        #   for_command=MacroStage.CONNECT
        #   macros={'j': 'myhost.sub.example.com', 'daemon_addr': '172.17.0.2'}
        self.logger.debug(f"decoding DefineMacro {self.data_raw.hex()=}")

        if not self.data_raw:
            raise ProtocolViolationCommandData(
                "DefineMacro command data must define a command (stage) for which they "
                "apply to."
            )

        stage = self.command_char_to_stage.get(self.data_raw[0:1])
        if stage is None:
            raise ProtocolViolationCommandData(
                f"Unknown command (stage) {self.data_raw[0:1]!r} for which macros "
                "apply to."
            )
        self.stage = stage

        macro_data_raw = self.data_raw[1:]

        if not macro_data_raw:
            self.logger.debug(f"No macros in DefineMacro for {stage=}")
            return

        if macro_data_raw[-1:] != b"\x00":
            raise ProtocolViolationCommandData(
                "DefineMacro command data must be NULL-terminated. "
                f"[data={self.data_raw!r}]"
            )

        items = _decode_array(macro_data_raw)
        if len(items) % 2 != 0:
            raise ProtocolViolationCommandData(
                "Macro data does not contain expected number of NULLs to split into "
                "symbol/value pairs"
            )

        for index in range(0, len(items), 2):
            symbol_raw, value_raw = items[index], items[index + 1]
            try:
                symbol, value = symbol_raw.decode("utf-8"), value_raw.decode("utf-8")
            except ValueError as e:
                raise ProtocolViolationCommandData(
                    f"Unable to decode macro: {symbol_raw=!r} {value_raw!r}",
                ) from e
            else:
                self.macros[symbol] = value

        self.logger.debug(f"Decoded macros: {self.macros}")
