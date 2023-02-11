# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

import pytest

from purepythonmilter.api.models import EsmtpArgsType, RequestProtocolFlags
from purepythonmilter.protocol.definitions import MacroStage
from purepythonmilter.protocol.payload import Payload
from purepythonmilter.protocol.responses import (
    AddRecipient,
    AddRecipientWithEsmtpArgs,
    AppendHeader,
    ChangeHeader,
    ChangeMailFrom,
    Continue,
    InsertHeader,
    OptionsNegotiateResponse,
    RejectWithCode,
    RemoveRecipient,
    ReplaceBodyChunk,
    TempFailWithCode,
    validate_headername_rfc5322,
)


def _assert_nothing_logged(records: Sequence[logging.LogRecord]) -> None:
    assert not [rec for rec in records if rec.levelno >= logging.INFO]


@pytest.mark.parametrize(
    ("flags", "payload"),
    [
        pytest.param(
            RequestProtocolFlags(),
            Payload(b"O\x00\x00\x00\x06\x00\x00\x01\x00\x00\x0f\xf7\xff"),
            id="default",
        ),
        pytest.param(
            RequestProtocolFlags(call_data=True),
            Payload(b"O\x00\x00\x00\x06\x00\x00\x01\x00\x00\x0f\xf5\xff"),
            id="enable-callback-data",
        ),
        pytest.param(
            RequestProtocolFlags(can_add_headers=True),
            Payload(b"O\x00\x00\x00\x06\x00\x00\x01\x01\x00\x0f\xf7\xff"),
            id="enable-action-add-headers",
        ),
    ],
)
def test_options_negotiate(
    flags: RequestProtocolFlags,
    payload: Payload,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert OptionsNegotiateResponse(protocol_flags=flags).encode() == payload
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("set_symbolslist_commands", "payload_expected"),
    [
        pytest.param(
            {MacroStage.END_OF_MESSAGE: {"i"}},
            Payload(
                b"O\x00\x00\x00\x06\x00\x00\x01\x00\x00\x0f\xf7\xff"
                b"\x00\x00\x00\x05i\x00"
            ),
            id="singular-request-symbol-i-on-end-of-message",
        ),
        pytest.param(
            {MacroStage.CONNECT: {"j", "{my}"}},
            Payload(
                b"O\x00\x00\x00\x06\x00\x00\x01\x00\x00\x0f\xf7\xff"
                b"\x00\x00\x00\x00j {my}\x00"
            ),
            id="singular-request-two-symbols-on-connect",
        ),
        pytest.param(
            {MacroStage.CONNECT: {"j"}, MacroStage.HELO: {"{my}"}},
            Payload(
                b"O\x00\x00\x00\x06\x00\x00\x01\x00\x00\x0f\xf7\xff"
                b"\x00\x00\x00\x00j\x00"
                b"\x00\x00\x00\x01{my}\x00"
            ),
            id="multiple-request-symbols-on-connect-and-helo",
        ),
    ],
)
def test_options_negotiate_with_symbolslist(
    set_symbolslist_commands: dict[MacroStage, set[str]],
    payload_expected: Payload,
    caplog: pytest.LogCaptureFixture,
) -> None:
    r = OptionsNegotiateResponse(
        protocol_flags=RequestProtocolFlags(),
        symbols_for_stage=set_symbolslist_commands,
    )
    assert r.encode() == payload_expected
    _assert_nothing_logged(caplog.records)


def test_response_str_repr() -> None:
    o = OptionsNegotiateResponse(protocol_flags=RequestProtocolFlags())
    assert str(o) == "OptionsNegotiateResponse"
    assert "logger=" not in repr(o)


def test_response_eq() -> None:
    o1 = OptionsNegotiateResponse(protocol_flags=RequestProtocolFlags())
    o2 = OptionsNegotiateResponse(protocol_flags=RequestProtocolFlags())
    # Would fail if logger attribute is not excluded in __eq__.
    assert o1 == o2


def test_continue(caplog: pytest.LogCaptureFixture) -> None:
    assert Continue().encode() == Payload(b"c")
    _assert_nothing_logged(caplog.records)


def test_reply_with_code_primary_only(caplog: pytest.LogCaptureFixture) -> None:
    assert TempFailWithCode(primary_code=(4, 7, 1)).encode() == Payload(b"y471\x00")
    assert RejectWithCode(primary_code=(5, 7, 1)).encode() == Payload(b"y571\x00")
    _assert_nothing_logged(caplog.records)


def test_reply_with_code_enhanced(caplog: pytest.LogCaptureFixture) -> None:
    assert TempFailWithCode(
        primary_code=(4, 7, 1), enhanced_code=(4, 7, 1)
    ).encode() == Payload(b"y471 4.7.1\x00")
    assert RejectWithCode(
        primary_code=(5, 7, 1), enhanced_code=(5, 7, 1)
    ).encode() == Payload(b"y571 5.7.1\x00")
    _assert_nothing_logged(caplog.records)


def test_reply_with_code_text(caplog: pytest.LogCaptureFixture) -> None:
    assert TempFailWithCode(primary_code=(4, 7, 1), text="foobar").encode() == Payload(
        b"y471 foobar\x00"
    )
    assert RejectWithCode(primary_code=(5, 7, 1), text="foobar").encode() == Payload(
        b"y571 foobar\x00"
    )
    _assert_nothing_logged(caplog.records)


def test_reply_with_code_text_and_enhanced(caplog: pytest.LogCaptureFixture) -> None:
    assert TempFailWithCode(
        primary_code=(4, 7, 1), enhanced_code=(4, 7, 1), text="foobar"
    ).encode() == Payload(b"y471 4.7.1 foobar\x00")
    assert RejectWithCode(
        primary_code=(5, 7, 1), enhanced_code=(5, 7, 1), text="foobar"
    ).encode() == Payload(b"y571 5.7.1 foobar\x00")
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("name_text_tuple", "expected_payload"),
    [
        pytest.param(
            ("Foo", "Bar"),
            Payload(b"hFoo\x00Bar\x00"),
            id="simple",
        ),
        pytest.param(
            ("Foo", ""),
            Payload(b"hFoo\x00\x00"),
            id="empty-headertext",
        ),
        pytest.param(
            ("Foo", "Bárม"),
            Payload(b"hFoo\x00B\xc3\xa1r\xe0\xb8\xa1\x00"),
            id="unciode-headertext",
        ),
        pytest.param(
            ("Fo~o", "Bar"),
            Payload(b"hFo~o\x00Bar\x00"),
            id="us-ascii-126-inclusive",
        ),
        pytest.param(
            ("Fo!o", "Bar"),
            Payload(b"hFo!o\x00Bar\x00"),
            id="us-ascii-33-inclusive",
        ),
    ],
)
def test_append_header_ok(
    name_text_tuple: tuple[str, str],
    expected_payload: Payload,
    caplog: pytest.LogCaptureFixture,
) -> None:
    name, text = name_text_tuple
    appendheader = AppendHeader(headername=name, headertext=text)
    assert appendheader.encode() == expected_payload
    _assert_nothing_logged(caplog.records)


def test_headername_validator_usascii_rfc5322() -> None:
    for c in range(0, 128):
        if c < 33 or c > 126:
            with pytest.raises(
                ValueError,
                match=re.compile(
                    r"Header field names must contain only US-ASCII printable "
                    r"characters with values between 33 and 126 \(RFC5322\)"
                ),
            ):
                validate_headername_rfc5322(chr(c))
        elif c == 58:
            with pytest.raises(
                ValueError,
                match=re.compile(
                    r"Header field names must not contain a colon \(RFC5322\)"
                ),
            ):
                validate_headername_rfc5322(chr(c))
        else:
            validate_headername_rfc5322(chr(c))


def test_headername_validator_extended_ascii_rfc5322() -> None:
    for c in range(128, 256):
        with pytest.raises(
            ValueError,
            match=re.compile(
                r"Header field names must contain only US-ASCII printable characters "
                r"with values between 33 and 126 \(RFC5322\)"
            ),
        ):
            validate_headername_rfc5322(chr(c))


invalid_headernames = [
    pytest.param(
        "", re.compile(r"Header field name cannot be empty\."), id="empty-headername"
    ),
    pytest.param(
        "X:ColonIllegal",
        re.compile(r"Header field names must not contain a colon \(RFC5322\)"),
        id="colon-not-allowed",
    ),
    pytest.param(
        "X No-Space",
        re.compile(
            r"Header field names must contain only US-ASCII printable characters with "
            r"values between 33 and 126 \(RFC5322\)"
        ),
        id="space-not-allowed",
    ),
]


@pytest.mark.parametrize(("headername", "match_re"), invalid_headernames)
def test_append_header_name_invalid(
    headername: str,
    match_re: re.Pattern[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ValueError, match=match_re):
        AppendHeader(headername=headername, headertext="Foo")
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("insertheader", "expected_payload"),
    [
        pytest.param(
            InsertHeader(headername="Foo", headertext="Bar", index=123),
            Payload(b"i\x00\x00\x00\x7bFoo\x00Bar\x00"),
            id="simple",
        ),
        pytest.param(
            InsertHeader(headername="Foo", headertext="", index=123),
            Payload(b"i\x00\x00\x00\x7bFoo\x00\x00"),
            id="empty-headertext",
        ),
        pytest.param(
            InsertHeader(headername="Foo", headertext="Bar", index=0),
            Payload(b"i\x00\x00\x00\x00Foo\x00Bar\x00"),
            id="simple-at-zero",
        ),
        pytest.param(
            InsertHeader(headername="Foo", headertext="Bárม", index=123),
            Payload(b"i\x00\x00\x00\x7bFoo\x00B\xc3\xa1r\xe0\xb8\xa1\x00"),
            id="unciode-headertext",
        ),
    ],
)
def test_insert_header_ok(
    insertheader: InsertHeader,
    expected_payload: Payload,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert insertheader.encode() == expected_payload
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("headername", "headertext", "index", "match_re"),
    [
        pytest.param(
            "",
            "Bar",
            123,
            re.compile(r"Header field name cannot be empty\."),
            id="empty-headername",
        ),
        pytest.param(
            "Foo",
            "Bar",
            -1,
            re.compile(r"Header index must be positive\."),
            id="index-negative",
        ),
    ],
)
def test_insert_header_invalid(
    headername: str,
    headertext: str,
    index: int,
    match_re: re.Pattern[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ValueError, match=match_re):
        InsertHeader(headername=headername, headertext=headertext, index=index)
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(("headername", "match_re"), invalid_headernames)
def test_insert_header_name_invalid(
    headername: str,
    match_re: re.Pattern[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ValueError, match=match_re):
        InsertHeader(headername=headername, headertext="Foo", index=1)
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("changeheader", "expected_payload"),
    [
        pytest.param(
            ChangeHeader(headername="Foo", headertext="Bar", nth_occurrence=123),
            Payload(b"m\x00\x00\x00\x7bFoo\x00Bar\x00"),
            id="simple",
        ),
        pytest.param(
            ChangeHeader(headername="Foo", headertext="", nth_occurrence=123),
            Payload(b"m\x00\x00\x00\x7bFoo\x00\x00"),
            id="empty-headertext",
        ),
        pytest.param(
            ChangeHeader(headername="Foo", headertext="Bar", nth_occurrence=0),
            Payload(b"m\x00\x00\x00\x00Foo\x00Bar\x00"),
            id="simple-at-zero",
        ),
        pytest.param(
            ChangeHeader(headername="Foo", headertext="Bárม", nth_occurrence=123),
            Payload(b"m\x00\x00\x00\x7bFoo\x00B\xc3\xa1r\xe0\xb8\xa1\x00"),
            id="unciode-headertext",
        ),
    ],
)
def test_change_header_ok(
    changeheader: ChangeHeader,
    expected_payload: Payload,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert changeheader.encode() == expected_payload
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("headername", "headertext", "nth_occurrence", "match_re"),
    [
        pytest.param(
            "",
            "Bar",
            123,
            re.compile(r"Header field name cannot be empty\."),
            id="empty-headername",
        ),
        pytest.param(
            "Foo",
            "Bar",
            -1,
            re.compile(r"Header index \(nth_occurrence\) must be positive\."),
            id="nth_occurrence-negative",
        ),
    ],
)
def test_change_header_invalid(
    headername: str,
    headertext: str,
    nth_occurrence: int,
    match_re: re.Pattern[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ValueError, match=match_re):
        ChangeHeader(
            headername=headername, headertext=headertext, nth_occurrence=nth_occurrence
        )
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(("headername", "match_re"), invalid_headernames)
def test_change_header_name_invalid(
    headername: str,
    match_re: re.Pattern[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ValueError, match=match_re):
        ChangeHeader(headername=headername, headertext="Foo", nth_occurrence=1)
    _assert_nothing_logged(caplog.records)


def test_add_recipient_ok() -> None:
    assert AddRecipient(
        recipient="purepythonmilter@gertvandijk.nl"
    ).encode() == Payload(b"+purepythonmilter@gertvandijk.nl\x00")


esmtp_args_params = [
    pytest.param(
        {"FOO": "BAR", "LOREM": "IPSUM"},
        b"FOO=BAR LOREM=IPSUM\x00",
        id="simple",
    ),
    pytest.param(
        {"FOO": "BAR", "LOREM": None},
        b"FOO=BAR LOREM\x00",
        id="esmtp-key-only",
    ),
]


@pytest.mark.parametrize(("esmtp_args", "expected_partial_payload"), esmtp_args_params)
def test_add_recipient_with_esmtp_args_ok(
    esmtp_args: EsmtpArgsType, expected_partial_payload: Payload
) -> None:
    assert AddRecipientWithEsmtpArgs(
        recipient="purepythonmilter@gertvandijk.nl", esmtp_args=esmtp_args
    ).encode() == Payload(
        b"2purepythonmilter@gertvandijk.nl\x00" + expected_partial_payload
    )


def test_remove_recipient_ok() -> None:
    assert RemoveRecipient(
        recipient="purepythonmilter@gertvandijk.nl"
    ).encode() == Payload(b"-purepythonmilter@gertvandijk.nl\x00")


def test_change_mail_from_ok() -> None:
    assert ChangeMailFrom(
        mail_from="purepythonmilter@gertvandijk.nl"
    ).encode() == Payload(b"epurepythonmilter@gertvandijk.nl\x00")


@pytest.mark.parametrize(("esmtp_args", "expected_partial_payload"), esmtp_args_params)
def test_change_mail_from_with_esmtp_args_ok(
    esmtp_args: EsmtpArgsType, expected_partial_payload: Payload
) -> None:
    assert ChangeMailFrom(
        mail_from="purepythonmilter@gertvandijk.nl", esmtp_args=esmtp_args
    ).encode() == Payload(
        b"epurepythonmilter@gertvandijk.nl\x00" + expected_partial_payload
    )


def test_replace_body_chunk_ok() -> None:
    assert ReplaceBodyChunk(chunk=b"foobar").encode() == Payload(b"bfoobar")


def test_replace_body_chunk_too_large() -> None:
    with pytest.raises(
        ValueError, match=re.compile(r"Length of 'chunk' must be <= 65535: 65536")
    ):
        ReplaceBodyChunk(chunk=b"1" * 65536).encode()
