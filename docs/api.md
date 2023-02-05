<!--
SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: Apache-2.0
-->

# Purepythonmilter API reference

***Note**: This document should be generated from source at some point.
It also lacks the documentation of all attributes currently.*

## `PurePythonMilter` class construction

A PurePythonMilter app is instantiated by providing the hooks to configure and which
flags to set.

Example:

```python
mymilter = PurePythonMilter(
    hook_on_connect=my_on_connect,
    can_add_headers=True,
)
```

### Hooks

Hooks point to a callable which need to have a return type annotation.

A hook callable must accept exactly one argument; one of the hook-specific Command
classes listed in the section below.

A `None` return type annotation will hint the MTA that the hook will not generate any
response and it will continue, so in that case you *must not* return a response.
This applies as possible return type of all of the hooks below.

- `hook_on_connect(cmd: Connect)`

  return type: `None` or any (subclass) of `VerdictOrContinue`
- `hook_on_helo(cmd: Helo)`

  return type: `None` or any (subclass) of `VerdictOrContinue`
- `hook_on_mail_from(cmd: MailFrom)`

  return type: `None` or any (subclass) of `VerdictOrContinue`
- `hook_on_rcpt_to(cmd: RcptTo)`

  return type: `None` or any (subclass) of `VerdictOrContinue`
- `hook_on_data(cmd: Data)`

  return type: `None` or any (subclass) of `VerdictOrContinue`
- `hook_on_header(cmd: Header)`

  return type: `None` or any (subclass) of `VerdictOrContinue`
- `hook_on_end_of_headers(cmd: EndOfHeaders)`

  return type: `None` or any (subclass) of `VerdictOrContinue`
- `hook_on_body_chunk(cmd: BodyChunk)`

  return type: `None` or any (subclass) of `VerdictOrContinue`, `SkipToNextStage`
- `hook_on_end_of_message(cmd: EndOfMessage)`

  return type: `None` or any (subclass) of `AbstractResponse`.
  `None` is translated into `Continue()`.
- `hook_on_abort(cmd: Abort)`

  return type: `None`
- `hook_on_quit(cmd: Quit)`

  return type: `None`
- `hook_on_unknown(cmd: Unknown)`

  return type: `None` or any (subclass) of `VerdictOrContinue`

### Flags

#### Hook flags

- `on_rcpt_to_include_rejected` (default: False)
- `headers_with_leading_space` (default: False)

#### Manipulation flags

- `can_add_headers` (default: False)

  in order to use `AppendHeader` or `InsertHeader` manipulations.
- `can_add_recipients` (default: False)

  in order to use the `AddRecipient` manipulation.
- `can_add_recipients_with_esmtp_args` (default: False)

  in order to use the `AddRecipientWithEsmtpArgs` manipulation.
- `can_change_body` (default: False)

  in order to use the `ReplaceBodyChunk` manipulation.
- `can_change_headers` (default: False)

  in order to use the `ChangeHeader` manipulation.
- `can_change_mail_from` (default: False)

  in order to use the `ChangeMailFrom` manipulation.
- `can_remove_recipients` (default: False)

  in order to use the `RemoveRecipient` manipulation.
- `can_quarantine` (default: False)

  in order to use the `Quarantine` response in `hook_on_end_of_message`.


## `Command`s

- *BaseCommand*
  - `Data`
  - `EndOfHeaders`
  - `EndOfMessage`
  - `Abort`
  - `Quit`
  - `QuitNoClose`
  - *BaseCommandWithData*
    - `OptionsNegotiate`
    - `Connect`
    - `Helo`
    - `Header`
    - `BodyChunk`
    - `Unknown`
    - `DefineMacro`
    - *BaseMailFromAndRcptTo*
      - `MailFrom`
      - `RcptTo`

## `Response`s

- *AbstractBaseResponse*
  - *AbstractManipulation*
    - *BaseChangeRecipient*
      - `AddRecipient`
      - `AddRecipientWithEsmtpArgs`
      - `RemoveRecipient`
    - *BaseHeaderManipulation*
      - `AppendHeader`
      - `InsertHeader`
      - `ChangeHeader`
    - `ReplaceBodyChunk`
    - `ChangeMailFrom`
  - *AbstractResponse*
    - *AbstractVerdict*
      - *BaseVerdictNoData*
        - `Accept`
        - `Reject`
        - `DiscardMessage`
        - `CauseConnectionFail`
      - *BaseReplyWithCode*
        - `RejectWithCode`
        - `TempFailWithCode`
      - `Quarantine`
    - *BaseResponseNoData*
      - `Continue`
      - `SkipToNextStage`
      - `Progress`
    - `OptionsNegotiateResponse`

`VerdictOrContinue` = `AbstractVerdict | Continue`
