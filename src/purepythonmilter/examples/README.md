<!--
SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: Apache-2.0
-->

# Run an example Milter app with Postfix in Docker

These steps will guide you to run an example app locally together with a Postfix
instance running in a Docker container.

## Requirements

- Have a modern Python at your current `PATH` (e.g. Python 3.10+).
  - Alternatively, obtain a modern Python and follow the steps below from a virtualenv
    using Pyenv+Direnv with the supplied `.envrc`; that's up to you.
- Docker installed with privileges to build and run containers as the current user on
  the system.
- Internet access for building the container that pulls in the base layer and downloads
  packages.
- Assumption of a default Docker network set up at `172.17.0.1/16` (for the steps below,
  or else adjust accordingly).
- No firewall in the way blocking connections from the Postfix container to your host.
- Have GNU Make (`make`) installed.

## Steps

1. Install Purepythonmilter, e.g. like this from sources:

   ```console
   $ git clone https://github.com/gertvdijk/purepythonmilter.git
   $ cd purepythonmilter

   # N.B. You may want to create and activate a Python virtualenv at this point.

   # This installs the package at the current location (`.`) with the `examples` option
   # to indicate extra dependencies to be installed.
   $ python -m pip install -e .[examples]
   ```

1. Run an example Milter app, bound to the Docker default network bridge interface with
   debug logging enabled.

   ```console
   $ python -m purepythonmilter.examples.debug_log_all \
       --bind-host 172.17.0.1 \
       --log-level=INFO
   ```

   💡 Change `--log-level=INFO` to `--log-level=DEBUG` and be ready to get a lot of
   output, perhaps relevant when testing.

1. Use the helpers in [`postfixtest/`](../../../postfixtest/) to build and run a Postfix
   instance in Docker.
   This will start a Postfix container named `purepythonmilter-postfixtest` and runs it
   in the foreground.

   ```console
   $ make -C postfixtest
   ```

   Wait until Postfix is ready, e.g.: when a line like this is printed:

   ```
   postfix/master[1]: daemon started -- version 3.5.6, configuration /etc/postfix
   ```

1. Send an email to `user@test.local` using your mail client (e.g. Thunderbird as SMTP
   outgoing server or [SWAKS][github-swaks]) to submit email to this Postfix instance.

   To find out what is the IP of the container, you can use the following command:

   ```console
   $ make --silent -C postfixtest get-ipv4
   ```

   One-liner to use SWAKS:

   ```console
   $ swaks --to user@test.local --server $(make --silent -C postfixtest get-ipv4)
   ```

1. Observe the output in the terminal where you started the Milter in step 2 as well as
   the output of Postfix.

   The Milter app should print now something like:

   ```
   INFO:purepythonmilter.server.milterserver:Milter server started, awaiting connections...
   INFO:debug_log_all:bb5bec76: On connect: args=ConnectionInfoArgsIPv4(hostname='[172.17.0.1]',
      addr=IPv4Address('172.17.0.1'), port=53286), macros={'j': ...
   INFO:debug_log_all:bb5bec76: On HELO: hostname=[172.17.0.1], macros={}
   INFO:debug_log_all:bb5bec76: On MAIL FROM: address=github@gertvandijk.nl,
      esmtp_args={'BODY': '8BITMIME', 'SIZE': ...
   INFO:debug_log_all:bb5bec76: On RCPT TO: address=user@test.local, esmtp_args={}, ...
   [...]
   INFO:debug_log_all:bb5bec76: On abort
   INFO:debug_log_all:bb5bec76: On quit
   ```

   You will still see errors on relaying the mail to `test.local`, but that does not
   exist and you can safely ignore that.
   It does not matter for the Milter.

1. Both the Postfix container and the Milter app can be stopped by pressing
   `<Ctrl>` + `C` in the terminal where they're running.

You have now seen a demonstration of the hooks that the Milter gives you with the
'debug_log_all' example app. 🎉

If you don't have a mail client at hand, you could use plain 'Old School' *telnet* too:

1. In another terminal, initiate a connection to Postfix using `telnet`.
   Note that the container has been given a dynamic IP address by Docker.
   ```console
   $ telnet "$(make --silent -C postfixtest get-ipv4)" 25
   ```
1. Observe the output in the terminal... (as above).
1. Back in the terminal where you started `telnet`, stop the connection to Postfix by
   either:
   - Type `QUIT` followed by pressing `<Enter>`, or
   - Quit the telnet client using the printed escape sequence (e.g. `<Ctrl>` + `]`),
     followed by typing `quit` and pressing `<Enter>`.


[github-swaks]: https://github.com/jetmore/swaks
