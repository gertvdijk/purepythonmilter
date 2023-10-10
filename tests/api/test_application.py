# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# pyright: reportPrivateUsage=false
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from purepythonmilter.api.application import ProgrammingError, PurePythonMilter
from purepythonmilter.protocol import commands, responses

if TYPE_CHECKING:
    from ..conftest import FakeMtaMilterSession


def test_fails_no_annotation_return_type() -> None:
    async def myhook(cmd: commands.Connect):  # type: ignore[no-untyped-def]  # noqa: ANN202
        return None

    with pytest.raises(ProgrammingError):
        PurePythonMilter(hook_on_connect=myhook)


def test_set_noreturn_callback_by_annotation() -> None:
    async def myhook(cmd: commands.Connect) -> None:
        return None

    ppm = PurePythonMilter(hook_on_connect=myhook)
    assert not ppm._request_proto_flags.reply_connect


def test_set_return_callback_by_annotation() -> None:
    async def myhook(cmd: commands.Connect) -> responses.BaseVerdictNoData:
        return responses.Accept()

    ppm = PurePythonMilter(hook_on_connect=myhook)
    assert ppm._request_proto_flags.reply_connect


@pytest.mark.asyncio()
async def test_basemilter_end_of_message_none_to_continue(
    fake_session: FakeMtaMilterSession,
) -> None:
    async def myhook(cmd: commands.EndOfMessage) -> None:
        return None

    ppm = PurePythonMilter(hook_on_end_of_message=myhook)
    basemilter = ppm._get_factory()(session=fake_session)
    ret = await basemilter.on_end_of_message(
        commands.EndOfMessage(data_raw=commands.CommandDataRaw(b""))
    )
    assert isinstance(ret, responses.Continue)


@pytest.mark.asyncio()
async def test_basemilter_end_of_message_not_none_kept(
    fake_session: FakeMtaMilterSession,
) -> None:
    async def myhook(cmd: commands.EndOfMessage) -> responses.Accept:
        return responses.Accept()

    ppm = PurePythonMilter(hook_on_end_of_message=myhook)
    basemilter = ppm._get_factory()(session=fake_session)
    ret = await basemilter.on_end_of_message(
        commands.EndOfMessage(data_raw=commands.CommandDataRaw(b""))
    )
    assert isinstance(ret, responses.Accept)
