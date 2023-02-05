<!--
SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: Apache-2.0
-->

# SMTP protocol recap

An SMTP conversation would typically look like this:

1. Client initiates a TCP connection to the server.
   - The MTA should talk first (client should wait!) and print a line with some basic
     indicators, e.g.:
     ```
     220 myhost.g3rt.nl ESMTP Postfix (Debian/GNU)
     ```
     where 2xx code indicates 'OK'.
   - The MTA may already reject the client at this point (e.g. IP blocklisted in RBLs).
   - Note that Postfix servers sending mail out are also SMTP clients.
1. Negotiate capabilities, e.g. upgrade connection security with StartTLS.
1. say `HELO mysmtpserver.g3rt.nl` (or `EHLO` instead of `HELO`)
   - The MTA may reject the connection already at this point (e.g. invalid HELO name).
1. say `MAIL FROM:<userx@y.foo.org>` to indicate the envelope sender (Return-Path).
   - The MTA may reject the sender address at this point (e.g. prohibit impersonation,
     sender address non-existence).
1. say `RCPT TO:<userc@d.bar.org>` for every recipient.
   - The MTA may reject the recipients (e.g. to deny relay access).
1. say `DATA` to proceed to sending headers.
1. say `HeaderName: header value` for every header.
1. say *empty newline* to proceed to sending the body.
1. Send the body as given a negotiated transfer encoding and policy, typically
   MIME-encoded with lines wrapped up to 72 characters.
1. say `.` on a line of its own to indicate the end of the message.

At any stage the MTA can reply to the client with a reply code, indicating extra
information, a successful completion or an error.
