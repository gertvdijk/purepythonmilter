# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations


class ProtocolViolation(BaseException):
    ...


class ProtocolViolationPacket(ProtocolViolation):
    ...


class ProtocolViolationPayload(ProtocolViolation):
    ...


class ProtocolViolationCommandData(ProtocolViolation):
    ...
