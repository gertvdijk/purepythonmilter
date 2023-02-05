# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging

import click

import purepythonmilter
from purepythonmilter import PurePythonMilter

logger: logging.LoggerAdapter[logging.Logger]


async def on_connect(cmd: purepythonmilter.Connect) -> None:
    logger.info(f"On connect: args={cmd.connection_info_args}, macros={cmd.macros}")


async def on_helo(cmd: purepythonmilter.Helo) -> None:
    logger.info(f"On HELO: hostname={cmd.hostname}, macros={cmd.macros}")


async def on_mail_from(cmd: purepythonmilter.MailFrom) -> None:
    logger.info(
        f"On MAIL FROM: address={cmd.address}, esmtp_args={cmd.esmtp_args}, "
        f"macros={cmd.macros}"
    )


async def on_rcpt_to(cmd: purepythonmilter.RcptTo) -> None:
    logger.info(
        f"On RCPT TO: address={cmd.address}, esmtp_args={cmd.esmtp_args}, "
        f"macros={cmd.macros}"
    )


async def on_data(cmd: purepythonmilter.Data) -> None:
    logger.info(f"On DATA: macros={cmd.macros}")


async def on_header(cmd: purepythonmilter.Header) -> None:
    logger.info(f"On header: name={cmd.name} text={cmd.text!r}, macros={cmd.macros}")


async def on_end_of_headers(cmd: purepythonmilter.EndOfHeaders) -> None:
    logger.info(f"On end of headers: macros={cmd.macros}")


async def on_body_chunk(cmd: purepythonmilter.BodyChunk) -> None:
    logger.info(f"On body chunk: length={len(cmd.data_raw)}, macros={cmd.macros}")


async def on_end_of_message(cmd: purepythonmilter.EndOfMessage) -> None:
    logger.info(f"On end of message: macros={cmd.macros}")


async def on_abort(cmd: purepythonmilter.Abort) -> None:
    logger.info("On abort")


async def on_quit(cmd: purepythonmilter.Quit) -> None:
    logger.info("On quit")


async def on_unknown(cmd: purepythonmilter.Unknown) -> None:
    logger.info(f"On unknown command: data_raw={cmd.data_raw!r}")


debug_log_all_milter = PurePythonMilter(
    name="debug_log_all",
    hook_on_connect=on_connect,
    hook_on_helo=on_helo,
    hook_on_mail_from=on_mail_from,
    hook_on_rcpt_to=on_rcpt_to,
    hook_on_data=on_data,
    hook_on_header=on_header,
    hook_on_end_of_headers=on_end_of_headers,
    hook_on_body_chunk=on_body_chunk,
    hook_on_end_of_message=on_end_of_message,
    hook_on_abort=on_abort,
    hook_on_quit=on_quit,
    hook_on_unknown=on_unknown,
    on_rcpt_to_include_rejected=True,
    restrict_symbols=None,
)
logger = debug_log_all_milter.logger


@click.command(
    context_settings=dict(
        show_default=True,
        max_content_width=200,
        auto_envvar_prefix="PUREPYTHONMILTER",
    )
)
@click.option(
    "--bind-host", default=purepythonmilter.DEFAULT_LISTENING_TCP_IP, show_envvar=True
)
@click.option(
    "--bind-port", default=purepythonmilter.DEFAULT_LISTENING_TCP_PORT, show_envvar=True
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    show_envvar=True,
)
@click.version_option(package_name="purepythonmilter", message="%(version)s")
def main(*, bind_host: str, bind_port: int, log_level: str) -> None:
    """
    This Milter app only logs all events for debugging purposes.
    """
    logging.basicConfig(level=getattr(logging, log_level))
    debug_log_all_milter.run_server(host=bind_host, port=bind_port)


if __name__ == "__main__":
    main()
