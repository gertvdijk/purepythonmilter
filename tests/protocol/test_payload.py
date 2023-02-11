# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from purepythonmilter.api.models import MilterServerConnectionID
from purepythonmilter.protocol.commands import OptionsNegotiate
from purepythonmilter.protocol.exceptions import ProtocolViolationPayload
from purepythonmilter.protocol.payload import Payload, PayloadDecoder

if TYPE_CHECKING:
    from collections.abc import Sequence


def _assert_nothing_logged(records: Sequence[logging.LogRecord]) -> None:
    assert not [rec for rec in records if rec.levelno >= logging.INFO]


@pytest.fixture()
def decoder() -> PayloadDecoder:
    connection_id = MilterServerConnectionID.generate()
    return PayloadDecoder(
        connection_id=connection_id,  # pyright: ignore PylancereportGeneralTypeIssues
    )


def test_decode_empty(
    decoder: PayloadDecoder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(RuntimeError):
        decoder.decode(Payload(b""))
    _assert_nothing_logged(caplog.records)


def test_decode_options_negotiate(
    decoder: PayloadDecoder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = Payload(b"O\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff")
    assert decoder.decode(payload) == (OptionsNegotiate, payload[1:])
    _assert_nothing_logged(caplog.records)


def test_decode_options_not_implemented(
    decoder: PayloadDecoder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ProtocolViolationPayload):
        decoder.decode(Payload(b"\x01\x00"))
    _assert_nothing_logged(caplog.records)
