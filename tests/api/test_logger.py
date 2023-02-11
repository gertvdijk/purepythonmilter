# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from purepythonmilter.api.logger import ConnectionContextLogger
from purepythonmilter.api.models import MilterServerConnectionID, connection_id_context

if TYPE_CHECKING:
    import pytest


def test_connectioncontext_logger_no_connection_id_no_extra(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = ConnectionContextLogger().get("mylogger")
    with caplog.at_level(logging.ERROR):
        logger.error("foo")
    messages = [rec.message for rec in caplog.records if rec.levelno >= logging.ERROR]
    assert messages == ["NONE: foo"]


def test_connectioncontext_logger_no_connection_id_but_extras(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = ConnectionContextLogger().get(
        "mylogger",
        extra_contexts={"myctx": "myval", "myint": 123},
    )
    with caplog.at_level(logging.ERROR):
        logger.error("foo")
    messages = [rec.message for rec in caplog.records if rec.levelno >= logging.ERROR]
    assert messages == ["NONE: foo [myctx=myval, myint=123]"]


def test_connectioncontext_logger_connection_id_at_start_extras(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = connection_id_context.set(MilterServerConnectionID(bytes=b"\x02" * 16))
    logger = ConnectionContextLogger().get(
        "mylogger",
        extra_contexts={"myctx": "myval", "myint": 123},
    )
    with caplog.at_level(logging.ERROR):
        logger.error("foo")
    connection_id_context.reset(token)
    messages = [rec.message for rec in caplog.records if rec.levelno >= logging.ERROR]
    assert messages == ["02020202: foo [myctx=myval, myint=123]"]


def test_connectioncontext_logger_connection_id_later_extras(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = ConnectionContextLogger().get(
        "mylogger",
        extra_contexts={"myctx": "myval", "myint": 123},
    )
    with caplog.at_level(logging.ERROR):
        token = connection_id_context.set(MilterServerConnectionID(bytes=b"\x04" * 16))
        logger.error("foo")
        connection_id_context.reset(token)
    messages = [rec.message for rec in caplog.records if rec.levelno >= logging.ERROR]
    assert messages == ["04040404: foo [myctx=myval, myint=123]"]
