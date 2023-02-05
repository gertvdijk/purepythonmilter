# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import TypeAlias

import attrs

from purepythonmilter.protocol.exceptions import ProtocolViolationPayload

from ..api import logger, models
from . import commands

Payload: TypeAlias = bytes


@attrs.define(auto_attribs=False, kw_only=True)
class PayloadDecoder:
    logger: logging.LoggerAdapter[logging.Logger] = attrs.field(init=False)
    _connection_id: models.MilterServerConnectionID = attrs.field()

    def __attrs_post_init__(self) -> None:
        self.logger = logger.ConnectionContextLogger().get(__name__)

    def decode(
        self, payload: Payload
    ) -> tuple[type[commands.BaseCommand], commands.CommandDataRaw]:
        if not payload:
            raise RuntimeError("Payload was empty")

        if (
            command_type := commands.chars_to_command_registry.get(payload[:1])
        ) is None:
            raise ProtocolViolationPayload(
                f"Received unknown Milter command, char={payload[:1]=!r} is not "
                "understood."
            )

        self.logger.debug(f"Got command {command_type}")
        return command_type, payload[1:]
