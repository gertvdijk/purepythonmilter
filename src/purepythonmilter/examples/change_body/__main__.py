# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

import click

from purepythonmilter import (
    DEFAULT_LISTENING_TCP_IP,
    DEFAULT_LISTENING_TCP_PORT,
    Continue,
    EndOfMessage,
    PurePythonMilter,
    ReplaceBodyChunk,
)

logger: logging.LoggerAdapter[logging.Logger]  # assigned below
_newbody: str = "foobar"  # global overridden in commandline parsing


async def on_end_of_message(cmd: EndOfMessage) -> Continue:
    global _newbody
    return Continue(manipulations=[ReplaceBodyChunk(chunk=_newbody.encode())])


change_body_milter = PurePythonMilter(
    name="change_body",
    hook_on_end_of_message=on_end_of_message,
    can_change_body=True,
)
logger = change_body_milter.logger


# Below is just mostly boilerplate for command line parsing.
@click.command(
    context_settings={
        "show_default": True,
        "max_content_width": 200,
        "auto_envvar_prefix": "PUREPYTHONMILTER",
    }
)
@click.option("--bind-host", default=DEFAULT_LISTENING_TCP_IP, show_envvar=True)
@click.option("--bind-port", default=DEFAULT_LISTENING_TCP_PORT, show_envvar=True)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    show_envvar=True,
)
@click.version_option(package_name="purepythonmilter", message="%(version)s")
@click.option("--newbody", default="foobar", show_envvar=True)
def main(*, bind_host: str, bind_port: int, log_level: str, newbody: str) -> None:
    """
    This Milter replaces the body with the value given in the `--newbody` parameter.
    """
    global _newbody
    logging.basicConfig(level=getattr(logging, log_level))
    _newbody = newbody
    change_body_milter.run_server(host=bind_host, port=bind_port)


if __name__ == "__main__":
    main()
