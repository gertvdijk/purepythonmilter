# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import pytest

from purepythonmilter.protocol import commands, responses

from ..conftest import FakeMtaMilterSession, MilterAppFactoryFixtureParams

pytestmark = pytest.mark.asyncio


def _assert_nothing_logged(records: Sequence[logging.LogRecord]) -> None:
    assert not [rec for rec in records if rec.levelno >= logging.INFO]


@pytest.mark.parametrize(
    ("cmd", "app_method"),
    [
        pytest.param(
            commands.Connect(
                data_raw=commands.CommandDataRaw(
                    b"[172.17.0.1]\x004\xc36172.17.0.1\x00"
                )
            ),
            "on_connect",
            id="connect",
        ),
        pytest.param(
            commands.Helo(data_raw=commands.CommandDataRaw(b"[172.17.0.1]\x00")),
            "on_helo",
            id="helo",
        ),
        pytest.param(
            commands.MailFrom(data_raw=commands.CommandDataRaw(b"<g@g3rt.nl>\x00")),
            "on_mail_from",
            id="mail-from",
        ),
        pytest.param(
            commands.RcptTo(data_raw=commands.CommandDataRaw(b"<g@g3rt.nl>\x00")),
            "on_rcpt_to",
            id="rcpt-to",
        ),
        pytest.param(
            commands.Data(data_raw=commands.CommandDataRaw(b"")),
            "on_data",
            id="data",
        ),
        pytest.param(
            commands.Header(
                data_raw=commands.CommandDataRaw(
                    b"From\x00Display Name <user@example.com>\x00"
                )
            ),
            "on_header",
            id="header",
        ),
        pytest.param(
            commands.EndOfHeaders(data_raw=commands.CommandDataRaw(b"")),
            "on_end_of_headers",
            id="end-of-headers",
        ),
        pytest.param(
            commands.BodyChunk(data_raw=commands.CommandDataRaw(b"foo")),
            "on_body_chunk",
            id="body-chunk",
        ),
        pytest.param(
            commands.EndOfMessage(data_raw=commands.CommandDataRaw(b"")),
            "on_end_of_message",
            id="end-of-message",
        ),
        pytest.param(
            commands.Unknown(data_raw=commands.CommandDataRaw(b"HELP\x00")),
            "on_unknown",
            id="unknown-command",
        ),
    ],
)
async def test_session_command_queue_no_macros_to_app(
    cmd: (
        commands.Connect
        | commands.Helo
        | commands.MailFrom
        | commands.RcptTo
        | commands.Data
        | commands.Header
        | commands.EndOfHeaders
        | commands.BodyChunk
        | commands.EndOfMessage
        | commands.Unknown
    ),
    app_method: str,
    fake_session: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    done_event = fake_session.queue_command(cmd)
    await done_event.wait()
    method = getattr(fake_session._app, app_method)
    method.assert_called()
    assert not cmd.macros
    _assert_nothing_logged(caplog.records)


@pytest.mark.parametrize(
    ("cmd", "app_method"),
    [
        pytest.param(
            commands.Abort(data_raw=commands.CommandDataRaw(b"")),
            "on_abort",
            id="abort",
        ),
        pytest.param(
            commands.Quit(data_raw=commands.CommandDataRaw(b"")),
            "on_quit",
            id="quit",
        ),
    ],
)
async def test_session_command_queue_commands_without_macro(
    cmd: commands.BaseCommand,
    app_method: str,
    fake_session: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    done_event = fake_session.queue_command(cmd)
    await done_event.wait()
    method = getattr(fake_session._app, app_method)
    method.assert_called()
    _assert_nothing_logged(caplog.records)


async def test_session_command_queue_not_implemented(
    fake_session_should_fail: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class NonExistingCommand(commands.BaseCommand):
        pass

    done_event = fake_session_should_fail.queue_command(NonExistingCommand())
    await asyncio.wait_for(done_event.wait(), 1)
    assert fake_session_should_fail._commands_consumer_task.done()
    assert isinstance(
        fake_session_should_fail._commands_consumer_task.exception(),
        NotImplementedError,
    )
    errors_logged = [rec for rec in caplog.records if rec.levelno >= logging.ERROR]
    assert len(errors_logged) == 1
    assert ("Got an exception in the commands consumer task.") in errors_logged[0].msg
    assert not [
        rec
        for rec in caplog.records
        if rec.levelno >= logging.INFO and rec.levelno != logging.ERROR
    ]


async def test_session_command_queue_macro_attached(
    fake_session: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    c1 = commands.DefineMacro(
        data_raw=commands.CommandDataRaw(b"Cj\x00myhost.sub.example.com\x00")
    )
    fake_session.queue_command(c1)
    c2 = commands.Connect(
        data_raw=commands.CommandDataRaw(b"[172.17.0.1]\x004\xc36172.17.0.1\x00")
    )
    e2 = fake_session.queue_command(c2)
    await e2.wait()
    assert c2.macros == {"j": "myhost.sub.example.com"}
    _assert_nothing_logged(caplog.records)


async def test_session_command_queue_macro_attached_wrong_stage_ignored(
    fake_session: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    c1 = commands.DefineMacro(
        # Macro for Connect stage,...
        data_raw=commands.CommandDataRaw(b"Cj\x00myhost.sub.example.com\x00")
    )
    fake_session.queue_command(c1)
    # ... but Data command follows, and thus...
    c2 = commands.Data(data_raw=commands.CommandDataRaw(b""))
    e2 = fake_session.queue_command(c2)
    await e2.wait()
    # ... should not attach macros.
    assert not c2.macros
    _assert_nothing_logged(caplog.records)


async def test_session_command_queue_timeout(
    fake_session: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    c1 = commands.DefineMacro(
        data_raw=commands.CommandDataRaw(b"Cj\x00myhost.sub.example.com\x00")
    )
    fake_session.queue_command(c1)
    # Wait for more than timeout
    await asyncio.sleep(0.02)
    c2 = commands.Connect(
        data_raw=commands.CommandDataRaw(b"[172.17.0.1]\x004\xc36172.17.0.1\x00")
    )
    e2 = fake_session.queue_command(c2)
    await e2.wait()
    assert c2.macros == {"j": "myhost.sub.example.com"}
    _assert_nothing_logged(caplog.records)


async def test_session_send_manipulations_before_end_of_message(
    fake_session: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert not fake_session._manipulations_sent

    fake_session._pending_manipulations.append(
        responses.AppendHeader(headername="Foo", headertext="Bar")
    )
    eom = commands.EndOfMessage(data_raw=commands.CommandDataRaw(b""))
    done_event = fake_session.queue_command(eom)
    await done_event.wait()

    assert fake_session._manipulations_sent
    _assert_nothing_logged(caplog.records)


class TwoCommandsMilterAppFactoryParams(MilterAppFactoryFixtureParams):
    """Fake app that would add a manipulation at on_connect and on_end_of_message."""

    return_on_connect: Any = responses.Continue(
        manipulations=[
            responses.AppendHeader(headername="X-On-Connect", headertext="Foo")
        ]
    )
    return_on_end_of_message: Any = responses.Continue(
        manipulations=[responses.AppendHeader(headername="X-On-EOM", headertext="Bar")]
    )


@pytest.mark.parametrize(
    "fake_app_factory",
    [pytest.param(TwoCommandsMilterAppFactoryParams())],
    indirect=True,
)
async def test_session_send_manipulations_before_end_of_message_merged(
    fake_session: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Assert that manipulations added at the on_connect callback (or any other basically)
    and on_end_of_message are combined and sent at on_end_of_message time.
    """
    assert not fake_session._manipulations_sent

    c1 = commands.Connect(
        data_raw=commands.CommandDataRaw(b"[172.17.0.1]\x004\xc36172.17.0.1\x00")
    )
    fake_session.queue_command(c1)
    c2 = commands.EndOfMessage(data_raw=commands.CommandDataRaw(b""))
    e2 = fake_session.queue_command(c2)
    await e2.wait()

    assert fake_session.responses_written == [
        TwoCommandsMilterAppFactoryParams.return_on_connect,
        responses.AppendHeader(headername="X-On-Connect", headertext="Foo"),
        responses.AppendHeader(headername="X-On-EOM", headertext="Bar"),
        TwoCommandsMilterAppFactoryParams.return_on_end_of_message,
    ]

    assert fake_session._manipulations_sent
    _assert_nothing_logged(caplog.records)


class InvalidTwoCommandsMilterAppFactoryParams(MilterAppFactoryFixtureParams):
    """
    Fake app that would erroneously add a manipulation at on_unknown, after an
    on_end_of_message.
    """

    return_on_unknown: Any = responses.Continue(
        manipulations=[
            responses.AppendHeader(headername="X-On-Unknown", headertext="Foo")
        ]
    )


@pytest.mark.parametrize(
    "fake_app_factory",
    [pytest.param(InvalidTwoCommandsMilterAppFactoryParams())],
    indirect=True,
)
async def test_session_send_manipulations_after_end_of_message_not_allowed(
    fake_session: FakeMtaMilterSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert not fake_session._manipulations_sent

    eom = commands.EndOfMessage(data_raw=commands.CommandDataRaw(b""))
    fake_session.queue_command(eom)
    later_command = commands.Unknown(data_raw=commands.CommandDataRaw(b"HELP\x00"))
    e2 = fake_session.queue_command(later_command)
    await e2.wait()

    assert fake_session._manipulations_sent
    assert len(fake_session._pending_manipulations) == 0

    warnings_logged = [rec for rec in caplog.records if rec.levelno >= logging.WARNING]
    assert len(warnings_logged) == 1
    assert (
        "Adding manipulations after End of Message callback is not allowed; ignoring: "
    ) in warnings_logged[0].msg
    assert not [
        rec
        for rec in caplog.records
        if rec.levelno >= logging.INFO and rec.levelno != logging.WARNING
    ]
