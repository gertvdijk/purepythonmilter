<!--
SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: Apache-2.0
-->

# Milter protocol high-level overview

Sendmail's libmilter documentation mixes both the network protocol and the C-level API a
lot.
[Postfix's Milter documentation][postfix-milter-readme] is great, but assumes prior
knowledge on Sendmail's Milter capabilities.

This page gives a fresh and more high-level overview of how a Milter operates.
As the Milter protocol is not described by an RFC, most of this information is derived
from public sources like Sendmail's libmilter source code, PyMilter documentation and
experimentation with Postfix's behaviour.

ℹ️ It is important to understand the basics of SMTP first; the Milter stages are a
superset of the SMTP stages, more or less.
See [`smtp-recap.md`](./smtp-recap.md) if you need some refreshment on SMTP.

## Milter protocol basics

During most of the steps during an SMTP conversation an MTA can call a command to a
configured Milter app that 'hooks into' the inspection, mangling and decision making.

Note that the MTA as mail server is a *client* on the operational level of a Milter and
the Milter app is run as a *server*.

An MTA-Milter connection shares the lifetime of the SMTP client-MTA connection; there's
one initiated by the MTA for each connection it receives. [^connection-reuse]
Every new connection starts with a negotiation of options.
The protocol is mostly synchronous, but allows for opt-out on commands during
negotiation.
The transport layer must already provide reliability and is typically a Unix socket or
TCP/IP.

Unlike SMTP, the Milter protocol is binary and not line based.

Packets are 'Length-Type-Value' encoded meaning that every packet must start with a
length field (unsigned 32-bit integer)...

- ... for the server (MTA), followed by a *command* (single byte character) and *command
  data* (command specific, arbitrary length and optional).

- ... for the client (Milter app) as response it is followed by an *response type*
 (single byte character) and *arguments* as data (action specific, arbitrary length and
 optional).

The client can send zero, one or multiple response packets in reply to a server command,
depending on the command and `negotiated protocol flags.

Similarly, the server can send one or multiple packets in one go without waiting for the
client to reply (again, depending on the negotiated protocol flags and the command).

String arguments to commands are basically (concatenated) NULL-terminated C-strings.

Some responses can be regarded as actions.
Some action`s indicate a final verdict, and some are intermediate.
An example; in reply to *End of message* command; modify multiple headers:
1. ADD_HEADER(...)
1. INSERT_HEADER(...)
1. CONTINUE

## Milter protocol terminology

- **callback** or **command**: the hook the MTA will call the Milter app on which
  corresponds to the transition to a new SMTP stage or an SMTP command given such as
  `RCPT TO` (repeated for every recipient).
  Callbacks can be enabled/disabled by the Milter app as desired for the application to
  increase performance.
- **macro**: a variable that the MTA may expose to the Milter app. See also *symbol*.
- **symbol**: the identifier of a macro, typically a string or a single character.
  E.g. `i` for Postfix queue ID, `{auth_authen}` for the username post-authentication.
  It seems that historically single character symbols were used and this was extended
  later with longer ones that include braces as safeguard.

## Milter protocol commands and stages

### Options negotiate (`SMFIC_OPTNEG`)

On every SMTP connection the MTA receives, it will open a new connection with the Milter
application.
Every new MTA-Milter connection will (re)start the negotiation with the Milter app and
the results are thereby local to the connection.
Part of the negotiation is the protocol version, MTA capabilities, desired protocol
flags and the set of callbacks the Milter app desires to opt-out for.

In other words, at this early stage the Milter and the MTA connection options are
exchanged and no MTA-connection or message specifics are included at this point.

The Milter-enabled MTA must send the command with data to indicate:

- Supported protocol flags for the Milter app.
  Some flags may be disabled server-side by MTA configuration or simply not implemented.
- Actions it may perform on messages.
  Some flags may be disabled server-side, e.g. to restrict a Milter to be read-only for
  security reasons.

The Milter application must respond to indicate:

- Desired protocol flags by the app.
  E.g. which callbacks to perform for this app, whether or not the app could send a
  reply for a command, whether or not to include the leading space for headers, etc.
- Actions it may perform on messages.
  E.g. hint the MTA the Milter may add headers to the message (but not modify the body).
- Optionally, and only if supported by the MTA as indicated by a flag, the list of
  desired macros that the MTA should include per protocol stage (from a list defined
  separately as macro stages).

### Macro (`SMFIC_MACRO`)

Defines a (list of) macro(s).

Usually called prior to every other regular command (except Options negotiate) to
provide more context.

### Connection established (`SMFIC_CONNECT`)

This callback will provide early SMTP connection level details such as the remote IP
address connecting to the MTA.

Note that this is prior to SMTP application-level negotiation such as upgrading the
connection security with e.g. StartTLS.

### HELO (`SMFIC_HELO`)

This callback will provide the HELO/EHLO name.

Macros may provide more SMTP connection level details such as TLS versions used (only in
case of plain TLS and not StartTLS).

### Envelope sender address (`SMFIC_MAIL`, SMTP: `MAIL FROM`)

This callback will provide the sender address (envelope-from).

Macros will provide more SMTP authentication level details and TLS connection details
may appear the first time in this stage if StartTLS is used.

### Recipients (`SMFIC_RCPT`, SMTP: `RCPT TO`)

Called for every recipient.
May also include recipients rejected by the MTA for other reasons (protocol flag
`SMFIP_RCPT_REJ`).

### DATA (`SMFIC_DATA`, SMTP: `DATA`)

Starting from this stage, the Postfix queue ID will be available.

### Header (`SMFIC_HEADER`)

Called for every header given in the DATA stage, providing the header name and value
(folded).

### End of headers (`SMFIC_EOH`)

Empty callback just called before the body is sent.

### Body (chunked, `SMFIC_BODY`)

Called multiple times if the body is larger than the chunk size.

### End of body/message (`SMFIC_BODYEOB`)

Empty callback after the body.

Most of the message manipulation actions can only take place in response to this
command.

### Unknown command (`SMFIC_UNKNOWN`)

Whenever an unrecognized SMTP command is sent to the MTA by a client.

### Abort (`SMFIC_ABORT`)

The MTA may want to abort the milter for reasons of an event that led to a final state
such as a connection error or a rejection that was effectuated by other means than this
Milter app.

Postfix appears to send this callback twice after responding with *Continue* at *End of
body*, the reason being unclear.

### Quit (`SMFIC_QUIT`)

When the SMTP command `QUIT` is sent by the client.

## Actions (responses) available

General actions:
- Continue (`SMFIR_CONTINUE`): neutral; proceed processing as normal.
- Accept (`SMFIR_ACCEPT`): positive final verdict; no further callbacks will happen.
- Reject (`SMFIR_REJECT`, optionally with a custom status code `SMFIR_REPLYCODE`):
  - on a connection: negative final verdict; reject/reset the connection
  - on a recipient command: reject the recipient (not the message)
  - on a message: negative final verdict; reject the message
- Tempfail (case of `SMFIR_REPLYCODE`): like Reject, but with a temporary failure code
  indicating that the client can try again later.
- Discard (`SMFIR_DISCARD`): pretends to the client that the message is accepted by the
  MTA, but it will actually *silently* drop it.
  Use with caution.
  Invalid on connections.
- Connection fail (`SMFIR_CONN_FAIL`): cause an SMTP connection failure.
- Progress (`SMFIR_PROGRESS`): a 'keepalive' response to inform the MTA the Milter app
  is still processing to prevent a reset by timeout from the MTA.
  May be sent multiple times.

On *End of message* callback:
- Change sender address (`SMFIR_CHGFROM`)
- Add recipient (`SMFIR_ADDRCPT`, variant: with ESMTP arguments `SMFIR_ADDRCPT_PAR`)
- Remove recipient (`SMFIR_DELRCPT`)
- Quarantine (`SMFIR_QUARANTINE`): puts the message in the hold queue.

On Body chunk commands:
- Replace body chunk (`SMFIR_REPLBODY`): replaces the chunk with the one in the response
  argument.
- Skip (`SMFIR_SKIP`): to signal the MTA to not call more commands for subsequent
  chunks; skip ahead to the *End of message* callback.

## Limitations & Caveats

### End of message is special

#### Manipulations only at End of message

Most of the message manipulation actions can only be sent in response to an End of
message command.

#### End of message cannot be disabled

There's no flag to disable the End of message command and a response by the Milter is
mandatory.

### No MTA-Milter connection until SMTP connected

This means that you don't expect to see a connection from the MTA to the Milter(s) prior
to the MTA receiving a connection.
As a result, any potential MTA-Milter connection issues appear not before the first SMTP
connection/message is handled by the MTA.

### Intermediate replies are unavailable

SMTP reply codes exists of a basic three-digit code, optionally along with *enhanced*
(or sometimes called *extended*) reply code and an optional textual description.

It appears that Milters are limited to replies with basic codes indicating negative
*completion* (first digit starting with 4 or 5) and intermediate replies are
unavailable.

References:
- [RFC 3463][rfc3463] "Enhanced Mail System Status Codes"
- RFC 5321 Simple Mail Transfer Protocol, sections [4.2][rfc5321-s4.2] and
  [4.3][rfc5321-s4.3]
- Wikipedia: [List of SMTP server return codes][wikipedia-smtp-returncodes]

### Slow Milter replies

If your Milter app takes long to decide, e.g. when doing an external processing task
that may take a long time, you can use the `Action.PROGRESS` as periodic keep-alive
reply to prevent the MTA-Milter connection to time out.

For example, at *End of body*, run an external virus checking service.
It may take 65 seconds, but the MTA-Milter timeout is 30s:

1. *time passes, less than MTA-Milter timeout setting*
1. Action.PROGRESS
1. *time passes, less than MTA-Milter timeout setting*
1. Action.CONTINUE

### Availability of commands and implicit requirements

- A Reject or Tempfail action may be preceded by a Reply code action (along with
  optional extended code and text desciption).
  If a (custom) reply status is not provided, it's up to the MTA what code/text to send
  to the client to do (unspecified?).

- The Quarantine action is only available at End of message stage and the reason
  parameter is required.

### Non-SMTP mail submissions

A Milter app may be involved for mail that is not submitted over SMTP.

Postfix emulates an SMTP session for Milter applications when it's configured as one of
the [non_smtpd_milters][postconf-non_smtpd_milters].
If so, then:

- Client must not send Reject/Tempfail action as reply to RCPT commands.

  > When a non_smtpd_milters application REJECTs or TEMPFAILs a recipient, Postfix will
  > report a configuration error, and mail will stay in the queue.

- > When new mail arrives via the sendmail(1) command line, the Postfix cleanup(8)
  > server pretends that the mail arrives with ESMTP from "localhost" with IP address
  > "127.0.0.1".

- > When new mail arrives via the qmqpd(8) server, the Postfix cleanup(8) server
  > pretends that the mail arrives with ESMTP, and uses the QMQPD client hostname and IP
  > address.

- > When old mail is re-injected into the queue with "postsuper -r", the Postfix
  > cleanup(8) server uses the same client information that was used when the mail
  > arrived as new mail.

### Inconsistent encoding of arrays in commands/responses

A single argument containing an array of strings is not encoded consistently and depends
on the command/response.
One example of using spaces as separator and a NULL as terminating character is the
requested list of symbols in Options negotiate.
In other cases the array may be encoded with a NULL separator; an example are the Mail
From / Rcpt To ESMTP arguments.
Note that the latter is space-separated on the SMTP-level. 🤯

## More on Macros and symbols

An MTA may send DEFINE_MACRO several times commands with multiple symbols.
The first byte of the argument data indicates the Milter command (stage) to which the
macros apply.
All bytes after are the key/value pairs encoded.
Each pair NULL-terminated and NULL-separated, passed as argument.
A symbol longer than a single character is wrapped in braces.

Macros may be defined just before sending the command at the following stages:
- `SMFIM_CONNECT` / `SMFIC_CONNECT`
- `SMFIM_HELO` / `SMFIC_HELO`
- `SMFIM_ENVFROM` / `SMFIC_MAIL`
- `SMFIM_ENVRCPT` / `SMFIC_RCPT`
- `SMFIM_DATA` / `SMFIC_DATA` & `SMFIC_HEADER`
- `SMFIM_EOH` / `SMFIC_EOH`
- `SMFIM_EOM` / `SMFIC_BODY`
- `SMFIM_EOM` / `SMFIC_BODYEOB`

Example:

```
C{mysymbol}NULLmyvalueNULL{othersymbol}NULLothervalueNULLiNULLABCD1234NULL
```

will be decoded as

- `C` applies to *Connection established* stage referring to `Command.CONNECTION_INFO`.
- `mysymbol` = `myvalue`
- `othersymbol` = `othervalue`
- `i` = `ABCD1234`

Sometimes command data arguments and macros appear to be redundant.

### Macro availability at stages

See your MTA's documentation on what macros are available at what stage for the Milter
apps.

It may be required to omit an opt-out for a command in the protocol flags for your app
even though you don't need to perform an action at that point.
For example, Postfix only exposes `{client_connections}` at the *Connection established*
stage, so if you want to vary on that in your action at a different stage, you must not
opt-out with the `NO_CONNECT` protocol flag, and save the macro value in your app's
state.

For optimization, the MTA can be requested to only send specific macros the Milter app
is interested in and is part of the *Options negotiate* response (see above).

### Options negotiate and symbols list (macros)

Sendmail's libmilter documentation and header files suggest that a symbols list can be
set using a response with code `l` as defined by `SMFIR_SETSYMLIST` in a list of
definitions titled `/* actions (replies) */`,... but that appears to be rather different
in practice.
In reality, the payload of the Options negotiate response is extended to include a
structure of `<4-byte macro stage ID><space-separated list of symbols>NULL`.

Example:

- HELO macro stage, request symbols `j` and `{my}`, and
- RCPT TO macro stage, request symbols `k` and `{other}`.

will be encoded as

```
\x00\x00\x00\x01j {my}\x00\x00\x00\x00\x00\x03k {other}\x00\x00
```

It appears there's no use of the defined `SMFIR_SETSYMLIST` response code in actual
implementations. 🤷

### Inability to disable the Define macro command

It seems there's no way to instruct the MTA to disable sending *Define macro* commands
completely.

When requesting for an empty set of symbols for a stage, and with the callback for a
stage disabled, Postfix seems to send a full *Define macro* command with the default
macros. 🤷

If a Milter would request a non-existent symbol, Postfix still calls the *Define macro*
command, but with an empty set. 😒

### MTA-Milter connection reuse

Have a look at the
[`SMFIC_QUIT_NC` command definition in libmilter][sendmail-libmilter-quit-nc], which
suggests that an MTA can reuse the existing connection to start a new 'session'.

```
#define SMFIC_QUIT_NC		'K'	/* QUIT but new connection follows *
```

Sendmail's libmilter seems to have this defined as separate state and does not close the
connection (but clears other state such as macros) as you'd expect.

However, there seems to be no use of this comand in both Sendmail MTA and Postfix. 😕

... Yet, there's a complaint in Postfix's source code that it's unable to reuse an
existing connection with a milter. 🤪

> XXX Sendmail 8 libmilter automatically closes the MTA-to-filter socket when it finds
> out that the SMTP client has disconnected. Because of this behavior, Postfix has to
> open a new MTA-to-filter socket each time an SMTP client connects.
> *<sup>[(source)][postfix-milter8c-comment-socket]</sup>*


[postfix-milter-readme]: https://www.postfix.org/MILTER_README.html
[rfc3463]: https://datatracker.ietf.org/doc/html/rfc3463
[rfc5321-s4.2]: https://datatracker.ietf.org/doc/html/rfc5321#section-4.2
[rfc5321-s4.3]: https://datatracker.ietf.org/doc/html/rfc5321#section-4.3
[wikipedia-smtp-returncodes]: https://en.wikipedia.org/wiki/List_of_SMTP_server_return_codes
[postconf-non_smtpd_milters]: https://www.postfix.org/postconf.5.html#non_smtpd_milters
[postfix-milter8c-comment-socket]: https://github.com/vdukhovni/postfix/blob/fe4e81b23b3ee76c64de73d7cb250882fbaaacb9/postfix/src/milter/milter8.c#L387-L390
[sendmail-libmilter-quit-nc]: https://salsa.debian.org/debian/sendmail/-/blob/0ad6934dd77ca9ef1e2a64a9862ceb9b56a7d3f8/include/libmilter/mfdef.h#L54

[^connection-reuse]: See the section "MTA-Milter connection reuse" below.
