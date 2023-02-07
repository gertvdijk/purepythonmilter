# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any, TypeAlias

from . import models

LoggingKwargs: TypeAlias = MutableMapping[str, Any]


# https://github.com/python/typeshed/issues/7855
if TYPE_CHECKING:
    _LoggerAdapterType = logging.LoggerAdapter[logging.Logger]  # pragma: nocover
else:
    _LoggerAdapterType = logging.LoggerAdapter


def _get_connection_id_or_none() -> models.MilterServerConnectionID | None:
    try:
        return models.connection_id_context.get()
    except LookupError:
        return None


class _LoggerAdapter(_LoggerAdapterType):
    def _format_context_trailer(self) -> str:
        assert hasattr(self, "extra") and self.extra is not None
        printable_contexts: dict[str, str] = {k: str(v) for k, v in self.extra.items()}
        del printable_contexts["connection_id"]
        if not printable_contexts:
            return ""
        keyvalues: list[str] = [f"{k}={v}" for k, v in printable_contexts.items()]
        keyvalues_str = ", ".join(keyvalues)
        return f" [{keyvalues_str}]"

    def process(self, msg: Any, kwargs: LoggingKwargs) -> tuple[Any, LoggingKwargs]:
        assert hasattr(self, "extra") and self.extra is not None
        # If we get instantiated with a connection ID context, let's use that.
        # Otherwise, try again at process time to obtain it.
        match self.extra.get("connection_id"):
            case models.MilterServerConnectionID() as connection_id:
                connection_id_short = connection_id.short
            case _:
                if (connection_id_now := _get_connection_id_or_none()) is None:
                    connection_id_short = "NONE"
                else:
                    connection_id_short = connection_id_now.short
        return f"{connection_id_short}: {msg}{self._format_context_trailer()}", kwargs


class ConnectionContextLogger:
    def get(
        self,
        name: str,
        *,
        extra_contexts: dict[str, Any] | None = None,
    ) -> logging.LoggerAdapter[logging.Logger]:
        _extra: dict[str, Any] = (
            dict() if extra_contexts is None else extra_contexts.copy()
        )
        _extra["connection_id"] = _get_connection_id_or_none()
        return _LoggerAdapter(logging.getLogger(name), _extra)
