# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

import click

from purepythonmilter import (
    DEFAULT_LISTENING_TCP_IP,
    DEFAULT_LISTENING_TCP_PORT,
    AppendHeader,
    Connect,
    ConnectionInfoArgsIPv4,
    ConnectionInfoArgsIPv6,
    Continue,
    PurePythonMilter,
)

logger: logging.LoggerAdapter[logging.Logger]  # assigned below
_headername: str = "X-UNSET"  # global overridden in commandline parsing


async def on_connect(cmd: Connect) -> Continue:
    """
    Demonstration: add a header without the need to implement an end_of_message
    callback, which would be required normally as mandated by the protocol.
    The MtaMilterSession will keep track of desired message manipulations and apply them
    at the later approriate end_of_message stage for you.
    """
    global _headername, logger
    match cmd.connection_info_args:  # noqa: E999
        case ConnectionInfoArgsIPv4() | ConnectionInfoArgsIPv6():
            ip = str(cmd.connection_info_args.addr)
            logger.info(f"on_connect(): adding header '{_headername}: {ip}'")
            return Continue(
                manipulations=[AppendHeader(headername=_headername, headertext=ip)]
            )
        case _:
            logger.warning(
                "on_connect(): connection socket family is not IP, skip adding header "
                f"{cmd.connection_info_args}"
            )
            return Continue()


append_header_ip_milter = PurePythonMilter(
    name="append_header_ip",
    hook_on_connect=on_connect,
    can_add_headers=True,
)
logger = append_header_ip_milter.logger


# Below is just mostly boilerplate for command line parsing.
@click.command(
    context_settings=dict(
        show_default=True,
        max_content_width=200,
        auto_envvar_prefix="PUREPYTHONMILTER",
    )
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
@click.option("--headername", default="X-MilterExample-Connect-IP", show_envvar=True)
def main(*, bind_host: str, bind_port: int, log_level: str, headername: str) -> None:
    """
    This Milter app appends a header with the value of the connecting IP.

    \b
    By default it adds it like this:
    X-MilterExample-Connect-IP: 1.2.3.4
    """
    global _headername
    logging.basicConfig(level=getattr(logging, log_level))
    _headername = headername
    append_header_ip_milter.run_server(host=bind_host, port=bind_port)


if __name__ == "__main__":
    main()
