# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import ipaddress
import logging
import struct
from typing import TYPE_CHECKING, Any, ClassVar, Final

import attrs
import pytest

from purepythonmilter.api import models
from purepythonmilter.protocol import definitions
from purepythonmilter.protocol.commands import (
    Abort,
    BaseCommand,
    BodyChunk,
    CommandDataRaw,
    Connect,
    DefineMacro,
    Header,
    Helo,
    MailFrom,
    OptionsNegotiate,
    Quit,
    RcptTo,
    Unknown,
    chars_to_command_registry,
)
from purepythonmilter.protocol.exceptions import ProtocolViolationCommandData

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

optneg_data_no_flags: Final[CommandDataRaw] = CommandDataRaw(
    # Just protocol version 6 and no other capabilities.
    b"\x00\x00\x00\x06\x00\x00\x00\x00\x00\x00\x00\x00"
)


def _make_options_negotiate_data(
    flag: definitions.ProtocolFlagsAllType | definitions.ActionFlags | None,
    version_mask: int = 0,
) -> CommandDataRaw:
    version_int = (
        int.from_bytes(optneg_data_no_flags[0:4], "big", signed=False) | version_mask
    )
    action_int = int.from_bytes(optneg_data_no_flags[4:8], "big", signed=False)
    proto_int = int.from_bytes(optneg_data_no_flags[8:12], "big", signed=False)
    match flag:
        case (
            definitions.ProtocolFlagsDisableCallback()
            | definitions.ProtocolFlagsOther()
        ):
            proto_int |= flag.value
        case definitions.ActionFlags():
            action_int |= flag.value
        case None:
            pass
    return CommandDataRaw(struct.pack("!III", version_int, action_int, proto_int))


def _assert_nothing_logged(records: Sequence[logging.LogRecord]) -> None:
    assert not [rec for rec in records if rec.levelno >= logging.INFO]


@pytest.mark.parametrize(
    ("data", "attributes_enabled"),
    [
        pytest.param(
            optneg_data_no_flags,
            [],
            id="empty",
        ),
        pytest.param(
            _make_options_negotiate_data(definitions.ActionFlags.ADD_HEADERS),
            [attrs.fields(models.MtaSupportsProtocolFlags).allows_add_headers],
            id="allows-add-headers",
        ),
        pytest.param(
            _make_options_negotiate_data(definitions.ProtocolFlagsDisableCallback.DATA),
            [attrs.fields(models.MtaSupportsProtocolFlags).disable_call_data],
            id="disable-call-data",
        ),
    ],
)
def test_options_negotiate_ok_but_warn(
    data: CommandDataRaw,
    attributes_enabled: Sequence[attrs.Attribute[models.MtaSupportsProtocolFlags]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    cmd_flags = OptionsNegotiate(data_raw=data).flags
    for flags_attribute in attrs.fields(models.MtaSupportsProtocolFlags):
        assert getattr(cmd_flags, flags_attribute.name) == (
            flags_attribute in attributes_enabled
        )
    # None of the protocol flags sent are normal.
    warnings_logged = [rec for rec in caplog.records if rec.levelno >= logging.WARNING]
    assert len(warnings_logged) == 1
    assert (
        "This MTA connection does not support all protocol flags. Are you using a "
        "modern Postfix? Milter may misbehave."
    ) in warnings_logged[0].msg


def test_options_negotiate_ok_normal_modern_postfix(
    caplog: pytest.LogCaptureFixture,
) -> None:
    OptionsNegotiate(data_raw=b"\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff")
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            CommandDataRaw(b"\x00"),
            id="empty",
        ),
        pytest.param(
            CommandDataRaw(b""),
            id="empty",
        ),
        pytest.param(
            CommandDataRaw(bytes(optneg_data_no_flags) + b"\x00"),
            id="too-long",
        ),
        pytest.param(
            CommandDataRaw(_make_options_negotiate_data(None, version_mask=7)),
            id="unsupported-protocol-version",
        ),
    ],
)
def test_options_negotiate_invalid(
    data: CommandDataRaw,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ProtocolViolationCommandData):
        OptionsNegotiate(data_raw=data)
    _assert_nothing_logged(caplog.records)


def test_command_str_repr() -> None:
    o = OptionsNegotiate(data_raw=b"\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff")
    assert str(o) == "OptionsNegotiate command [data=<12 bytes>]"
    assert "logger=" not in repr(o)


def test_command_eq() -> None:
    o1 = OptionsNegotiate(data_raw=b"\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff")
    o2 = OptionsNegotiate(data_raw=b"\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff")
    # Would fail if logger attribute is not excluded in __eq__.
    assert o1 == o2


@pytest.mark.parametrize(
    ("data", "stage", "expected_macros"),
    [
        pytest.param(
            CommandDataRaw(b"C"),
            definitions.MacroStage.CONNECT,
            {},
            id="for-connect-empty",
        ),
        pytest.param(
            CommandDataRaw(
                b"Cj\x00myhost.sub.example.com\x00{daemon_addr}\x00172.17.0.2\x00"
            ),
            definitions.MacroStage.CONNECT,
            {"j": "myhost.sub.example.com", "{daemon_addr}": "172.17.0.2"},
            id="for-connect-with-data",
        ),
        pytest.param(
            CommandDataRaw(b"H"),
            definitions.MacroStage.HELO,
            {},
            id="for-helo-empty",
        ),
        pytest.param(
            CommandDataRaw(b"U"),
            definitions.MacroStage.UNKNOWN,
            {},
            id="for-unknown-empty",
        ),
    ],
)
def test_define_macro_ok(
    data: CommandDataRaw,
    stage: definitions.MacroStage,
    expected_macros: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    dm = DefineMacro(data_raw=data)
    assert dm.stage == stage
    assert dm.macros == expected_macros
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            CommandDataRaw(b""),
            id="empty",
        ),
        pytest.param(
            CommandDataRaw(b"\x01"),
            id="invalid-command-without-data",
        ),
        pytest.param(
            CommandDataRaw(b"\x01j\x00myhost.sub.example.com\x00"),
            id="invalid-command-with-data",
        ),
        pytest.param(
            CommandDataRaw(
                b"Cj\x00myhost.sub.example.com\x00{daemon_addr}\x00172.17.0.2"
            ),
            id="data-missing-null-termination",
        ),
        pytest.param(
            CommandDataRaw(
                b"Cj\x00myhost.sub.example.com{daemon_addr}\x00172.17.0.2\x00"
            ),
            id="data-invalid-num-separators",
        ),
        pytest.param(
            CommandDataRaw(
                b"Cj\x00myhost.sub.example.com\x00{\xffaemon_addr}\x00172.17.0.2\x00"
            ),
            id="utf8-impossible-byte-3.5.1-symbol",
        ),
        pytest.param(
            CommandDataRaw(
                b"Cj\x00myhost.sub.example.com\x00{daemon_addr}\x00172.\xff7.0.2\x00"
            ),
            id="utf8-impossible-byte-3.5.1-value",
        ),
    ],
)
def test_define_macro_invalid(
    data: CommandDataRaw,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ProtocolViolationCommandData):
        DefineMacro(data_raw=data)
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("data", "expected_connection_info_args"),
    [
        pytest.param(
            CommandDataRaw(b"[172.17.0.1]\x004\xc36172.17.0.1\x00"),
            models.ConnectionInfoArgsIPv4(
                hostname="[172.17.0.1]",
                addr=ipaddress.IPv4Address("172.17.0.1"),
                port=49974,
            ),
            id="example-ipv4-no-reverse",
        ),
        pytest.param(
            CommandDataRaw(b"myhostname.mydomain.tld\x004\xc36172.17.0.1\x00"),
            models.ConnectionInfoArgsIPv4(
                hostname="myhostname.mydomain.tld",
                addr=ipaddress.IPv4Address("172.17.0.1"),
                port=49974,
            ),
            id="example-ipv4-with-reverse",
        ),
        pytest.param(
            CommandDataRaw(
                b"[2607:f8b0:4864:20::748]\x006\xa3\x162607:f8b0:4864:20::748\x00"
            ),
            models.ConnectionInfoArgsIPv6(
                hostname="[2607:f8b0:4864:20::748]",
                addr=ipaddress.IPv6Address("2607:f8b0:4864:20::748"),
                port=41750,
            ),
            id="example-ipv6-no-reverse",
        ),
        pytest.param(
            CommandDataRaw(
                b"mail-oi1-x234.google.com\x006\x82.2607:f8b0:4864:20::234\x00"
            ),
            models.ConnectionInfoArgsIPv6(
                hostname="mail-oi1-x234.google.com",
                addr=ipaddress.IPv6Address("2607:f8b0:4864:20::234"),
                port=33326,
            ),
            id="example-ipv6-with-reverse",
        ),
        pytest.param(
            CommandDataRaw(b"ignored_hostname\x00L\x00\x00/run/mysock\x00"),
            models.ConnectionInfoArgsUnixSocket(
                path="/run/mysock",
            ),
            id="example-unix-socket",
        ),
        pytest.param(
            CommandDataRaw(b"ignored_hostname\x00L\x00\x00/run/\xc3\xb1ysock\x00"),
            models.ConnectionInfoArgsUnixSocket(
                path="/run/ñysock",
            ),
            id="example-unix-socket-utf8",  # TODO: verify this is sent as listed here.
        ),
        pytest.param(
            CommandDataRaw(b"unknown\x00U"),
            models.ConnectionInfoUnknown(description="unknown"),
            id="unknown",
        ),
    ],
)
def test_connect_ok(
    data: CommandDataRaw,
    expected_connection_info_args: models.ConnectionInfoArgs,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert Connect(data_raw=data).connection_info_args == expected_connection_info_args
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            CommandDataRaw(b"[172.17.0.1]"),
            id="structure",
        ),
        pytest.param(
            CommandDataRaw(b"[172.17.0.1]\x00"),
            id="structure",
        ),
        pytest.param(
            CommandDataRaw(b"[172.17.0.1]\x004\xc361\x00"),
            id="socket-data-too-short",
        ),
        pytest.param(
            CommandDataRaw(b"[256.17.0.1]\x004\xc36256.17.0.1\x00"),
            id="ipv4-invalid",
        ),
        pytest.param(
            CommandDataRaw(b"[172.17.0.1]\x004\xc36172.\xff7.0.1\x00"),
            id="ipv4-invalid-char-ip",
        ),
        pytest.param(
            CommandDataRaw(b"[172.\xff.0.1]\x004\xc36172.17.0.1\x00"),
            id="ipv4-invalid-char-hostname",
        ),
        pytest.param(
            CommandDataRaw(
                b"[2607:f8b0:4864:20::748]\x006\xa3\x162607:f8b0:4864:20:::748\x00"
            ),
            id="ipv6-invalid",
        ),
        pytest.param(
            CommandDataRaw(
                b"[2607:f8b0:4864:20::748]\x006\xa3\x162607:f8b0:4864:20::11748\x00"
            ),
            id="ipv6-invalid",
        ),
        pytest.param(
            CommandDataRaw(
                b"[2607:f8b0:4864:20::748]\x006\xa3\x162607:f8b0:4864:20::\xff\x00"
            ),
            id="ipv6-invalid-char-ip",
        ),
        pytest.param(
            CommandDataRaw(
                b"[2607:f8b0:4864:20::\xff]\x006\xa3\x162607:f8b0:4864:20::748\x00"
            ),
            id="ipv6-invalid-char-hostname",
        ),
        pytest.param(
            CommandDataRaw(b"[\xff.17.0.1]\x004\xc36172.17.0.1\x00"),
            # https://www.cl.cam.ac.uk/~mgk25/ucs/examples/UTF-8-test.txt
            id="hostname-utf8-impossible-byte-3.5.1",
        ),
        pytest.param(
            CommandDataRaw(b"[172.17.0.1]\x005\xc36172.17.0.1\x00"),
            id="unsupported-socket-family-ipv5",
        ),
        pytest.param(
            CommandDataRaw(b"ignored_hostname\x00L\x00\x00/run/\xffysock\x00"),
            id="unix-socket-invalid-char",
        ),
    ],
)
def test_connect_invalid(
    data: CommandDataRaw,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ProtocolViolationCommandData):
        Connect(data_raw=data)
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("data", "expected_hostname"),
    [
        pytest.param(
            CommandDataRaw(b"\x00"),
            "",
            id="hostname-empty",
        ),
        pytest.param(
            CommandDataRaw(b"foobar\x00"),
            "foobar",
            id="hostname-string",
        ),
        pytest.param(
            CommandDataRaw(b"[172.17.0.1]\x00"),
            "[172.17.0.1]",
            id="hostname-ip",
        ),
        pytest.param(
            CommandDataRaw(b"foo\xe0\xb8\xbfar\x00"),
            r"foo\xe0\xb8\xbfar",  # not foo฿ar
            id="hostname-string-valid-utf8-to-ascii",
        ),
        pytest.param(
            CommandDataRaw(b"foo\xffbar\x00"),
            r"foo\xffbar",
            # https://www.cl.cam.ac.uk/~mgk25/ucs/examples/UTF-8-test.txt
            id="hostname-string-utf8-impossible-byte-backslashreplace",
        ),
    ],
)
def test_helo_ok(
    data: CommandDataRaw,
    expected_hostname: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert Helo(data_raw=data).hostname == expected_hostname
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            CommandDataRaw(b""),
            id="hostname-empty-no-null-termination",
        ),
        pytest.param(
            CommandDataRaw(b"foobar"),
            id="hostname-string-no-null-termination",
        ),
    ],
)
def test_helo_invalid(
    data: CommandDataRaw,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ProtocolViolationCommandData):
        Helo(data_raw=data)
    _assert_nothing_logged(caplog.records)


# No type annotations for pytest.ParameterSet, sigh. 😞
def generate_mail_from_and_rcpt_to_testparams_ok() -> Generator[Any, None, None]:
    for cmd_class in (MailFrom, RcptTo):
        yield from [
            pytest.param(
                cmd_class,
                CommandDataRaw(b"<g@g3rt.nl>\x00"),
                "g@g3rt.nl",
                {},
                id=f"{cmd_class.__name__}-address-string",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b"<g@g3rt.nl>\x00FOO=BAR\x00SIZE=1234\x00"),
                "g@g3rt.nl",
                {"FOO": "BAR", "SIZE": "1234"},
                id=f"{cmd_class.__name__}-simple-esmtp-args",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b"<g@g3rt.nl>\x00FOO=BAR\x00FOO=BAZ\x00"),
                "g@g3rt.nl",
                {"FOO": "BAZ"},
                id=f"{cmd_class.__name__}-esmtp-args-last-key-wins",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(
                    b"<bounce+1-local=domain.tld@example.com>\x00BODY=8BITMIME"
                    b"\x00SMTPUTF8\x00"
                ),
                "bounce+1-local=domain.tld@example.com",
                {"BODY": "8BITMIME", "SMTPUTF8": None},
                id=f"{cmd_class.__name__}-esmtp-args-value-is-optional",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b"<g@g3rt.nl>\x00FOO=\xc3\xb1BAR\x00SIZE=1234\x00"),
                "g@g3rt.nl",
                {"FOO": "ñBAR", "SIZE": "1234"},
                id=f"{cmd_class.__name__}-non-ascii-esmtp-arg-value",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b"<g\xff@g3rt.nl>\x00"),
                r"g\xff@g3rt.nl",
                {},
                # https://www.cl.cam.ac.uk/~mgk25/ucs/examples/UTF-8-test.txt
                id=f"{cmd_class.__name__}-address-utf8-impossible-backslashreplace",
            ),
        ]


@pytest.mark.parametrize(
    ("cmd_class", "data", "expected_address", "expected_esmtp_args"),
    generate_mail_from_and_rcpt_to_testparams_ok(),
)
def test_mail_from_and_rcpt_to_ok(
    cmd_class: type[MailFrom | RcptTo],
    data: CommandDataRaw,
    expected_address: str,
    expected_esmtp_args: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    cmd = cmd_class(data_raw=data)
    assert cmd.address == expected_address
    assert cmd.esmtp_args == expected_esmtp_args
    _assert_nothing_logged(caplog.records)


def generate_mail_from_and_rcpt_to_testparams_angle_brackets() -> (
    Generator[Any, None, None]
):
    for cmd_class in (MailFrom, RcptTo):
        yield from [
            pytest.param(
                cmd_class,
                CommandDataRaw(b"g@g3rt.nl\x00"),
                "g@g3rt.nl",
                {},
                id=f"{cmd_class.__name__}-plain-address",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b"g@g3rt.nl\x00FOO=BAR\x00SIZE=1234\x00"),
                "g@g3rt.nl",
                {"FOO": "BAR", "SIZE": "1234"},
                id=f"{cmd_class.__name__}-plain-address-with-esmtp-args",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b"<g@g3rt.nl\x00"),
                "<g@g3rt.nl",
                {},
                id=f"{cmd_class.__name__}-right-angle-bracket-missing",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b"g@g3rt.nl>\x00"),
                "g@g3rt.nl>",
                {},
                id=f"{cmd_class.__name__}-left-angle-bracket-missing",
            ),
        ]


@pytest.mark.parametrize(
    ("cmd_class", "data", "expected_address", "expected_esmtp_args"),
    generate_mail_from_and_rcpt_to_testparams_angle_brackets(),
)
def test_mail_from_and_rcpt_to_angle_brackets(
    cmd_class: type[MailFrom | RcptTo],
    data: CommandDataRaw,
    expected_address: str,
    expected_esmtp_args: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    cmd = cmd_class(data_raw=data)
    assert cmd.address == expected_address
    assert cmd.esmtp_args == expected_esmtp_args
    warnings_logged = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert len(warnings_logged) == 1
    assert (
        f"Address in Mail From / Rcpt To '{expected_address}' appears not "
        "enclosed in angle brackets."
    ) in warnings_logged[0].msg
    assert not [
        rec
        for rec in caplog.records
        if rec.levelno >= logging.INFO and rec.levelno != logging.WARNING
    ]


def generate_mail_from_and_rcpt_to_testparams_invalid() -> Generator[Any, None, None]:
    for cmd_class in (MailFrom, RcptTo):
        yield from [
            pytest.param(
                cmd_class,
                CommandDataRaw(b"\x00"),
                id=f"{cmd_class.__name__}-address-empty",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b""),
                id=f"{cmd_class.__name__}-address-empty-no-null-termination",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(b"<g@g3rt.nl>"),
                id=f"{cmd_class.__name__}-address-no-null-termination",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(
                    b"<g@g3rt.nl>\x00F\xc3\xb3\xc3\xb3=BAR\x00SIZE=1234\x00"
                ),
                id=f"{cmd_class.__name__}-non-ascii-esmtp-arg-name",
            ),
            pytest.param(
                cmd_class,
                CommandDataRaw(
                    CommandDataRaw(b"<g@g3rt.nl>\x00FOO==BAR\x00SIZE=1234\x00"),
                ),
                id=f"{cmd_class.__name__}-multiple-key-value-separators",
            ),
        ]


@pytest.mark.parametrize(
    ("cmd_class", "data"),
    generate_mail_from_and_rcpt_to_testparams_invalid(),
)
def test_mail_from_rcpt_to_invalid(
    cmd_class: type[MailFrom | RcptTo],
    data: CommandDataRaw,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ProtocolViolationCommandData):
        cmd_class(data_raw=data)
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("data", "name", "text"),
    [
        pytest.param(
            CommandDataRaw(b"From\x00Display Name <user@example.com>\x00"),
            "From",
            "Display Name <user@example.com>",
            id="simple-from-header",
        ),
        pytest.param(
            CommandDataRaw(b"From\x00Display \xe0\xb8\x84ame <user@example.com>\x00"),
            "From",
            "Display คame <user@example.com>",
            id="utf8-header-rfc6532",
        ),
        pytest.param(
            CommandDataRaw(b"X-Spam-Level\x00\x00"),
            "X-Spam-Level",
            "",
            id="empty-header-value-is-ok",
        ),
        pytest.param(
            CommandDataRaw(b"From\x00Display Name\xff <user@example.com>\x00"),
            "From",
            r"Display Name\xff <user@example.com>",
            # https://www.cl.cam.ac.uk/~mgk25/ucs/examples/UTF-8-test.txt
            id="utf8-impossible-byte-backslashreplace",
        ),
        pytest.param(
            CommandDataRaw(
                b"Subject\x00Dit servicebericht bevat essenti\xeble informatie\x00"
            ),
            "Subject",
            r"Dit servicebericht bevat essenti\xeble informatie",
            id="utf8-invalid-subject-backslashreplace",
        ),
    ],
)
def test_header_ok(
    data: CommandDataRaw,
    name: str,
    text: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    hdr = Header(data_raw=data)
    assert hdr.name == name
    assert hdr.text == text
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            CommandDataRaw(b"From\x00Display Name <user@example.com>"),
            id="structure",
        ),
        pytest.param(
            CommandDataRaw(b"From Display Name <user@example.com>\x00"),
            id="structure",
        ),
        pytest.param(
            CommandDataRaw(b"From: Display Name <user@example.com>\x00"),
            id="structure",
        ),
        pytest.param(
            CommandDataRaw(b"From: Display Name <user@example.com>"),
            id="structure",
        ),
    ],
)
def test_header_invalid(
    data: CommandDataRaw,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ProtocolViolationCommandData):
        Header(data_raw=data)
    _assert_nothing_logged(caplog.records)


test_commands_nodata_params = [
    pytest.param(
        CommandDataRaw(b"\x00"),
        id="null-byte",
    ),
    pytest.param(
        CommandDataRaw(b"foobar"),
        id="something-else",
    ),
    pytest.param(
        CommandDataRaw(b"foobar\x00"),
        id="something-else",
    ),
]


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            CommandDataRaw(b""),
            id="empty-should-work",
        ),
        pytest.param(
            CommandDataRaw(b"foo"),
            id="simple-content",
        ),
        pytest.param(
            CommandDataRaw(b"foo\xffbar"),
            id="do-not-care-about-encoding",
        ),
    ],
)
def test_body_chunk(
    data: CommandDataRaw,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bdc = BodyChunk(data_raw=data)
    assert bdc.data_raw == data
    _assert_nothing_logged(caplog.records)


def test_abort_ok(caplog: pytest.LogCaptureFixture) -> None:
    Abort(data_raw=CommandDataRaw(b""))
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "data",
    test_commands_nodata_params,
)
def test_abort_invalid(data: CommandDataRaw, caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ProtocolViolationCommandData):
        Abort(data_raw=CommandDataRaw(data))
    _assert_nothing_logged(caplog.records)


def test_quit_ok(caplog: pytest.LogCaptureFixture) -> None:
    Quit(data_raw=CommandDataRaw(b""))
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "data",
    test_commands_nodata_params,
)
def test_quit_invalid(data: CommandDataRaw, caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ProtocolViolationCommandData):
        Quit(data_raw=CommandDataRaw(data))
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            CommandDataRaw(b""),
            id="empty-should-work",
        ),
        pytest.param(
            CommandDataRaw(b"HELP\x00"),
            id="unknown-command-as-data",
        ),
        pytest.param(
            CommandDataRaw(b"HELP"),
            id="not-null-terminated",
        ),
        pytest.param(
            CommandDataRaw(b"foo\xffbar\x00"),
            id="do-not-care-about-encoding",
        ),
    ],
)
def test_unknown_ok(data: CommandDataRaw, caplog: pytest.LogCaptureFixture) -> None:
    u = Unknown(data_raw=data)
    assert u.data_raw == data.removesuffix(b"\x00")
    _assert_nothing_logged(caplog.records)


def test_command_registry_populated() -> None:
    assert len(chars_to_command_registry) == 15  # noqa: PLR2004
    assert all(len(char) == 1 for char in chars_to_command_registry)


@pytest.mark.parametrize(
    "char",
    [
        pytest.param(
            b"O",
            id="taken-by-OptionsNegotiate",
        ),
        pytest.param(
            b"",
            id="length-invalid-zero",
        ),
        pytest.param(
            b"ZZ",
            id="length-invalid-more-than-one",
        ),
    ],
)
def test_command_registry_fails_definition_time(char: bytes) -> None:
    with pytest.raises(ValueError):

        class CommandWithCharInvalid(  # pyright: ignore PylancereportUnusedClass
            BaseCommand
        ):
            command_char: ClassVar[bytes] = char

    # NOTE: do not attempt to define a class with an actual valid/available char as it
    # would affect the rest of the test run. 😕
