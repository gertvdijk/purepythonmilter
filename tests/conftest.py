# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import attrs
import pytest
import pytest_asyncio

from purepythonmilter.api import models
from purepythonmilter.api.application import PurePythonMilter
from purepythonmilter.api.interfaces import (
    AbstractMilterApp,
    AbstractMtaMilterConnectionHandler,
    AbstractMtaMilterSession,
    MilterAppFactory,
)
from purepythonmilter.protocol import payload, responses
from purepythonmilter.server import session

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Generator


logger = logging.getLogger(__name__)


@pytest.fixture()
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Same reason as in https://stackoverflow.com/a/72104554, we need to override the
    built-in fixture properly close the loop in teardown. Not before all tasks have been
    awaited to finish. Similar to high-level functions as asyncio.run() do.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    for i in range(1, 51):
        pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        if n_tasks := len(pending_tasks):
            if i % 5 == 0:
                logger.warning(f"Still {n_tasks} pending tasks...")
            logger.debug(f"{pending_tasks=}")
            loop.run_until_complete(asyncio.sleep(0.001 * i))
        else:
            break
    else:
        pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        raise Exception(  # noqa: TRY002
            f"Still having { len(pending_tasks)} pending tasks... {pending_tasks=}"
        )
    loop.close()


@pytest.fixture()
def full_conversation_packets() -> list[bytes]:
    return [
        # 0: Options negotiate
        b"\x00\x00\x00\rO\x00\x00\x00\x06\x00\x00\x01\xff\x00\x1f\xff\xff",
        # 1: Connect
        b"\x00\x00\x00\x1cC[172.17.0.1]\x004\x81|172.17.0.1\x00",
        # 2: Helo
        b"\x00\x00\x00\x0eH[172.17.0.1]\x00",
        # 3: Mail From
        b"\x00\x00\x00:M<purepythonmilter@gertvandijk.nl>\x00BODY=8BITMIME\x00"
        b"SIZE=466\x00",
        # 4: Rcpt To
        b"\x00\x00\x00\x10R<g@test.local>\x00",
        # 5: Data
        b"\x00\x00\x00\x01T",
        # 6, 7: Header, another Header
        b"\x00\x00\x00BLMessage-ID\x00<5037ef9b-0616-86fd-0561-b0f3c198edc4"
        b"@gertvandijk.nl>\x00",
        b"\x00\x00\x00YLUser-Agent\x00Mozilla/5.0 (X11; Linux x86_64; rv:91.0) "
        b"Gecko/20100101\n Thunderbird/91.10.0\x00",
        # 8: End of Headers
        b"\x00\x00\x00\x01N",
        # 9: Body Chunk
        b"\x00\x00\x00\x19Btest\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n",
        # 10: End of Message
        b"\x00\x00\x00\x01E",
        # 11: Some random Unknown command
        b"\x00\x00\x00\x06UHELP\x00",
        # 12: Abort, another Abort
        b"\x00\x00\x00\x01A",
        b"\x00\x00\x00\x01A",
        # 13: Quit
        b"\x00\x00\x00\x01Q",
    ]


class MilterAppFactoryFixtureParams:
    return_on_connect: Any = None
    return_on_end_of_message: Any = responses.Continue()
    return_on_unknown: Any = None


if TYPE_CHECKING:

    class FixtureRequest:
        param: MilterAppFactoryFixtureParams | None

else:
    FixtureRequest = Any


@pytest_asyncio.fixture  # pyright: ignore [reportUnknownMemberType, reportUntypedFunctionDecorator]  # noqa: E501
async def fake_app_factory(
    request: FixtureRequest,  # indirect parameter to specify mock return values
) -> MilterAppFactory:
    mocked_return_on_connect: Any = None
    # application.PurePythonMilter should translate None into responses.Continue().
    mocked_return_on_end_of_message = responses.Continue()
    mocked_return_on_unknown: Any = None
    if hasattr(request, "param") and request.param is not None:
        mocked_return_on_connect = request.param.return_on_connect
        mocked_return_on_end_of_message = request.param.return_on_end_of_message
        mocked_return_on_unknown = request.param.return_on_unknown

    def app_factory(session: AbstractMtaMilterSession) -> AbstractMilterApp:
        ppm = PurePythonMilter()
        factory = ppm._get_factory()
        app = factory(session=session)
        app.on_connect = AsyncMock(return_value=mocked_return_on_connect)  # type: ignore[method-assign]  # noqa: E501
        app.on_helo = AsyncMock(return_value=None)  # type: ignore[method-assign]
        app.on_mail_from = AsyncMock(return_value=None)  # type: ignore[method-assign]
        app.on_rcpt_to = AsyncMock(return_value=None)  # type: ignore[method-assign]
        app.on_data = AsyncMock(return_value=None)  # type: ignore[method-assign]
        app.on_header = AsyncMock(return_value=None)  # type: ignore[method-assign]
        app.on_end_of_headers = AsyncMock(return_value=None)  # type: ignore[method-assign]  # noqa: E501
        app.on_body_chunk = AsyncMock(return_value=None)  # type: ignore[method-assign]
        app.on_end_of_message = AsyncMock(return_value=mocked_return_on_end_of_message)  # type: ignore[method-assign]  # noqa: E501
        app.on_abort = AsyncMock(return_value=None)  # type: ignore[method-assign]
        app.on_quit = AsyncMock(return_value=None)  # type: ignore[method-assign]
        app.on_unknown = AsyncMock(return_value=mocked_return_on_unknown)  # type: ignore[method-assign]  # noqa: E501
        return app

    return app_factory


@pytest_asyncio.fixture  # pyright: ignore [reportUnknownMemberType, reportUntypedFunctionDecorator]  # noqa: E501
async def fake_socket_connection(
    fake_app_factory: MilterAppFactory,
) -> AbstractMtaMilterConnectionHandler:
    class FakeStreamWriter:
        def write(self, data: bytes) -> None:
            pass

        def writelines(self, data: bytes) -> None:
            pass

        def write_eof(self) -> None:
            pass

        def can_write_eof(self) -> bool:
            return True

        def close(self) -> None:
            pass

        def is_closing(self) -> bool:
            return False

        async def wait_closed(self) -> None:
            pass

        def get_extra_info(self, name: str) -> None:
            pass

        async def drain(self) -> None:
            pass

    def sever_callback(connection_id: models.MilterServerConnectionID) -> None:
        pass

    @attrs.define(auto_attribs=False)
    class FakeSocketConnection(AbstractMtaMilterConnectionHandler):
        _connection_id = models.MilterServerConnectionID.generate()
        _reader = asyncio.StreamReader()
        _writer = FakeStreamWriter()  # type: ignore[assignment]
        app_factory: MilterAppFactory = attrs.field()
        _server_on_close_cb: Callable[
            [models.MilterServerConnectionID], None
        ] = sever_callback

        @property
        def id_(self) -> models.MilterServerConnectionID:
            return self._connection_id

        async def keep_reading_packets(self) -> None:
            return None

        async def write_response(
            self, payload: payload.Payload, *, drain: bool = False
        ) -> None:
            return None

        async def close_bottom_up(self) -> None:
            return None

        async def close_top_down(self) -> None:
            return None

        def session_error_callback(self, *, exception: BaseException) -> None:
            return None

    return FakeSocketConnection(app_factory=fake_app_factory)


@attrs.define(auto_attribs=False)
class FakeMtaMilterSession(session.MtaMilterSession):
    """
    MtaMilterSession that does not send responses down to the
    MtaMilterConnectionHandler, but saves those which would have been sent.
    """

    responses_written: list[
        (responses.AbstractResponse | responses.AbstractManipulation)
    ] = attrs.field(init=False, factory=list)

    async def _send_response(
        self, response: responses.AbstractResponse | responses.AbstractManipulation
    ) -> None:
        self.responses_written.append(response)


@pytest_asyncio.fixture  # pyright: ignore [reportUnknownMemberType, reportUntypedFunctionDecorator]  # noqa: E501
async def fake_session(
    fake_socket_connection: AbstractMtaMilterConnectionHandler,
) -> AsyncGenerator[FakeMtaMilterSession, None]:
    mms = FakeMtaMilterSession(
        socket_connection=fake_socket_connection,  # pyright: ignore [reportGeneralTypeIssues] # noqa: E501
        # Let's set a very short timeout to not have tests run so long.
        queue_reader_timeout_seconds=0.01,
    )

    yield mms
    if (
        mms._commands_consumer_task.done()
        and (exc := mms._commands_consumer_task.exception()) is not None
    ):
        raise exc
    assert not mms._commands_consumer_task.done()
    mms._commands_consumer_task.cancel()


@pytest_asyncio.fixture  # pyright: ignore [reportUnknownMemberType, reportUntypedFunctionDecorator]  # noqa: E501
async def fake_session_should_fail(
    fake_socket_connection: AbstractMtaMilterConnectionHandler,
) -> AsyncGenerator[FakeMtaMilterSession, None]:
    mms = FakeMtaMilterSession(
        socket_connection=fake_socket_connection  # pyright: ignore [reportGeneralTypeIssues] # noqa: E501
    )
    yield mms
    assert mms._commands_consumer_task.done()
    assert mms._commands_consumer_task.exception() is not None
