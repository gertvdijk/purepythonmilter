<!--
SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: Apache-2.0
-->

# Design

The *MilterServer* class manages asyncio's event loop which is instructed to open a
listening socket and what to call on incoming connections.
It also registers the process signal handlers and takes care of the administration of
pending connections.
(The raw TCP/Socket connection is handled by asyncio's event loop.)

A method of the *MtaMilterConnectionHandler* is set as callback for new connections.
It then manages the connection between the MTA and the Milter server on the lower level,
e.g. reading from and writing to socket and delegation the decoding/encoding of the
packets.

A more high-level Milter-protocol connection handler is available as *MtaMilterSession*
and deals with application-layer logic of a Milter server.
This class receives decoded **Command**s in its queue and deals with outgoing
**Response**s pushing them down the socket via *MtaMilterConnectionHandler*.

At the start of each connection (session), the *MtaMilterSession* will instantiate an
'app' using a factory.
The 'app' (implementing the *AbstractMilterApp*) is where the business logic takes
place, of which parts are to be provided by the user of this library.
For any **Command** or event the *MtaMilterSession* calls the `on_*` methods on the app
instance.
It also provides some conveniences like normalization of header names, carries the
macros along the Milter stages, etc.

The *PurePythonMilter* builds the object implementing an *AbstractMilterApp* class from
the API.
It also inspects the code of the desired hooks to toggle the most efficient protocol
flags in negotiation with the MTA.
For example, if there's no hook for `on_connect`, it asks the MTA to skip the on-connect
callback.

In case you don't like the 'batteries included' that come with the above, you could
perhaps reuse/subclass the *MtaMilterSession* from this library as an alternative.
Going deeper than that does not make much sense probably; it's basically boilerplate
around asyncio's event loop and protocol definitions.

## Opt-in philosophy

*"You will only get what you asked for."*

The Milter protocol is opt-out-driven, but the purepythonmilter APIs reverses this for
performance reasons.

- All callbacks will be disabled, unless declared as desired.
- All available "no reply" protocol flags will be enabled, unless a response is declared
  as desired.
  It makes MTA callbacks to be asynchronous by default where possible.
- 'Meta' commands like *Options negotiate* and *Define macro* are hidden and the latter
  is provided for you as attribute `macros` of the actual command.

## Modern-only approach

The Milter protocol seems to suffer heavily from historic changes and some Sendmail
specific implementation details.
Instead of trying to be compatible, purepythonmilter assumes the use of a modern Postfix
with Milter protocol version 6.

To make the implementation as clean as possible, purepythonmilter may assume or mandate
the use of the latest Python version (3.10 at time of writing) and [mypy-strict] typing
annotations.
While this approach reduces the compatibility heavily, it's common nowadays to use
different packaging (i.e. containers, AppImage, etc.) for operating systems that lack
the latest version of Python.

This approach keeps focus on correct and complete Milter implementation rather than
spending time on maintaining compatibility with older CPython.

## Production-ready examples

This library is not *just* a library; it's supposed to provide some examples available
as runnables (entrypoints) that should work in a production setting.
Integration tests ensure that these examples should always be runnable and up-to-date.

## Layered decoding of the Milter protocol

Incoming packets (commands):

- TCP/Unix socket data is taken as **Packet**s ('Length-Type-Value' encoded datagrams)
  by the *MtaConnection* using asyncio's low-level [StreamReader][asyncio-streamreader].

- The *PacketDecoder* decodes the length bytes, strips it off and returns zero, one or
  more 'Type-Value' **Payload**s as a generator.
  The *PacketDecoder* is stateful in the sense that it stores incomplete packet data and
  reassembles them as needed.

- A **Payload** is decoded to **Command**-**CommandData** pair by the *PayloadDecoder*.

- The *PayloadDecoder* calls the **Command**-specific decoder to decode the
  **CommandData** as attributes to the **Command**.

- The *MtaMilterConnectionHandler* then puts the decoded **Command**s on a
  *CommandQueue* ([asyncio.Queue][asyncio-queue]) of the *MtaMilterSession*.

Outgoing packets (responses):

- The *MtaMilterSession* receives a **Response** object from the Milter app as
  return value of the method called (as per *AbstractMilterApp* interface).

- This **Response** object is then passed to the *MtaMilterConnectionHandler* writer
  where it's encoded to a payload.

- The *MtaMilterConnectionHandler* writer then encodes the **Payload** into one or more
  **Packet**s and writes them on the socket to the MTA using asyncio's
  [StreamWriter][asyncio-streamwriter].

Common for both incoming and outgoing:

- At any stage and layer a *ProtocolViolation* may be raised on input error(s).
- At any stage and layer a *NotImplementedError* may be raised on known (defined), but
  unsupported input.


[asyncio-streamreader]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader
[asyncio-streamwriter]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter
[asyncio-queue]: https://docs.python.org/3/library/asyncio-queue.html
[mypy-strict]: https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict
