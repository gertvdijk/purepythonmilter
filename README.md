<!--
SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: Apache-2.0
-->

# A modern pure-Python Milter framework

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org/)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict-blue)](https://mypy.readthedocs.io/en/stable/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v1.json)](https://github.com/charliermarsh/ruff)
[![Imports: isort](https://img.shields.io/badge/imports-isort-%231674b1?labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Hadolint](https://img.shields.io/badge/hadolint-passing-brightgreen)](https://github.com/hadolint/hadolint)
[![ShellCheck](https://img.shields.io/badge/ShellCheck-passing-brightgreen)](https://www.shellcheck.net/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-brightgreen)](https://www.apache.org/licenses/LICENSE-2.0)
[![REUSE compliant](https://img.shields.io/badge/reuse-compliant-brightgreen)](https://reuse.software/)

Mail servers ([MTA][wikipedia-mta]s) like [Postfix][postfix-home] and
[Sendmail][sendmail-org-home] can connect to an external filter process, called a
'Milter', for actions to take during an incoming SMTP transaction.
You may consider it like a plugin on the mail server software using callbacks over a TCP
or UNIX socket.

A Milter can have any custom condition to reject/tempfail/discard a message, manipulate
headers and/or body and more.
This can be useful if you require custom validations or manupulative actions before mail
is accepted and that is unavailable in ~~your MTA's~~ Postfix's built-in features.
The use of a Milter would typically be the right choice when it comes to complex
decision making on accepting mail 'before queue' with conditions on headers or the
message body.

*Purepythonmilter* aims to be a modern, Postfix-first, high-quality, strictly typed
framework and library.
And then all of that with an easy to use API and a high-performance asynchronous
embedded server.

## Getting started 🚀

Install Purepythonmilter, e.g. using `pip`:

```console
$ pip install purepythonmilter
```

Self-descriptive example Milter app:

```python
import purepythonmilter as ppm


async def on_mail_from(cmd: ppm.MailFrom) -> ppm.VerdictOrContinue:
    if cmd.address.lower().endswith("@example.com"):
        return ppm.RejectWithCode(primary_code=(5, 7, 1), text="not allowed here!")
    return ppm.Continue()


mymilter = ppm.PurePythonMilter(name="mymilter", hook_on_mail_from=on_mail_from)
mymilter.run_server(host="127.0.0.1", port=9000)
```

### Configuration with Postfix

1. Start your Milter application or run one of the examples directly — see
   [`examples/`][examples-readme].
2. Start a Postfix instance with a configuration like
   `smtpd_milters = inet:127.0.0.1:9000` (replace IP address and port number
   accordingly).

### Run an example Milter app with Postfix in Docker

Described here 👉 [`examples/README.md`][examples-readme].

## *Example* use cases for a Milter app 💡

- From-header and envelope sender (Return-Path) alignment validation, for compliance
  with DMARC ([RFC7489 section 3.1][dmarc-rfc7489-sec31]) or reasons of preventing abuse
  (impersonation).
  Pevent sending such messages out by rejecting non-compliant messages on submission
  time already and incude a descriptive error message to the user.
- Encrypt sensitive connection/account information and attach that in a custom header
  value for outbound mail.
  In case of abuse, the information can be decrypted by an operator from the raw mails
  concerned and eliminates the need to store this data centrally for all mail.
- Cryptographically sign outgoing email or verify signatures of incoming email with some
  custom scheme.
  *In case you don't like the existing commonly used [OpenDKIM Milter][opendkim-readme]
  and want to implement your own DKIM signer/verifier.*

## What about PyMilter?

Purepythonmilter was written as an alternative to, and, out of frustration with it.
[PyMilter] is not type annotated (mypy), has signal handling issues (for me), the
dependency on a [hand-crafted Python-C-extension][pymilter-miltermodule-c] linking to
Sendmail's libmilter and no offering of a binary package ([wheel][pep-427]) to ease
installation. 😥

*By the way, did you know that Sendmail is — yes even in 2023 — written in K&R C
(predating ANSI-C)?[^sendmail-relnotes-kr-c-deprecation]* 🙈

So, yeah, that's the short version of why I started this project. 🤓

## Documentation 📖

- [`docs/design.md`](./docs/design.md) — design and intents of this project. 🧠
- [`docs/api.md`](./docs/api.md) — API documentation
- [`docs/milter-protocol.md`](./docs/milter-protocol.md) — raw protocol notes. ✍️
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — for development setup and contribution
  guidelines

## Limitations

- Any functionality requiring intermediary responses (such as 'progress') is not yet
  implemented in the API.
- Any functionality that requires carrying state over phases is not yet supported in the
  API. (e.g. combining input from two different hooks)
- Mail headers are not 'folded'/'unfolded', but given or written as-is.
- UNIX domain sockets are not supported for the Milter server to listen on (TCP is).

## Feedback 💬

This project is very new and feedback is very much welcome!
Please don't hesitate to [file an issue][github-new-issue], drop an idea or ask a
question in the [discussions][github-new-discussion].

[Ideas & Feature Requests][github-ideas-feature-requests] are in there too. 💡

Alternatively, just drop me a message at `github@gertvandijk.nl`. 📬

## When *not* to use a Milter

If you want to accomplish something that could be done using a custom dynamic
lookup in Postfix, such as message routing or policy lookups.
Postfix offers quite some built-in dynamic lookup types and a Milter is probably *not*
what you're looking for.
The Milter protocol is relatively complex and its use may not be required for your use
case.

Be sure to also have a look at implementing your own custom dynamic lookup table in
Postfix using the [socketmap protocol][postfix-socketmap-table] or policy delegation
with the much simpler [policy delegation protocol][postfix-smtpd-policy-protocol].
Most of the email's and connection's *metadata* is available there too.
For example, the [postfix-mta-sts-resolver] uses the former and the SPF policy daemon
[pypolicyd-spf] uses the latter.
Sometimes the use of a Milter may still be considered; for example, the SPF verification
filter [spf-milter] is implemented using the Milter protocol.

For content inspection, there's Postfix's [Content filter][postfix-filter-readme], but
beware that it's running 'after queue'.
It takes quite some orchestration to avoid bounces and correctly feed the mail back into
Postfix.

Another aspect to consider is MTA support.
While the alternatives for Postfix listed above are still Postfix-specific, other more
generic lookup methods also exist.
For example, a dynamic DNS lookup could be much better adopted when migrating to another
MTA than any of the above.

Example use cases which are *possible* to implement using a Milter, but what could also
be accomplished using alternative — likely simpler — ways:

- Inject custom headers to add information on which `smtpd` instance the email was
  received for routing/classifications later.
  This would typically be done using Postfix's policy delegation returning
  `PREPEND headername: headertext` as action.
- Validate sender restrictions for a data backend type not supported by the Postfix,
  such as interacting with an HTTP REST API / webhooks.
  Again, policy delegation may be much simpler, but if conditions involve mail contents,
  then you may need a Milter still.
- Custom centralized rate limiting and billing in an email hosting platform with several
  account tiers.
  And similarly for this one, policy delegation is probably much simpler.
- A read-only Milter that logs in a structured way and perhaps with certain conditions.
  This would eliminate parsing Postfix's text log files, well, for incoming connections
  at least.
  [Freeaqingme/ClueGetter] is such an application using the Milter protocol for a part
  of the functionality.

## Alternatives to Purepythonmilter

Python alternatives appear to be unmaintained and no longer actively supported for
years.

- [python-libmilter]: marked as ['no longer supporting'][python-libmilter-readme-note],
  as of late 2022.
- [PpyMilter]: Python 2-only (last commit 2015).

Alternatives in other programming languages without a dependency on Sendmail's libmilter
are:

- [indymilter]: an asynchronous Milter library written in **Rust**.
- [Sendmail::PMilter][sendmail-pmilter]: a pure-**Perl** implementation (last release
  2011).
- [emersion/go-milter]: a Milter library written in **Go** (in active development).
- [phalaaxx/milter]: another Milter library written in **Go** (last commit 2020).
- [andybalholm/milter]: a simple framework for writing milters written in **Go** (last
  commit 2016).
- [nightcode/jmilter]: a Milter library written in **Java**.
- [sendmail-jilter]: another Milter library written in **Java** (last release 2011).
- [milterjs][Atlantis-Software/milterjs]: a Milter library written in **Javascript**
  (last release 2018).

Other relevant projects (not really reusable libraries):
[phalaaxx/ratemilter], [phalaaxx/pf-milters], [mschneider82/milterclient],
[andybalholm/grayland], [Freeaqingme/ClueGetter].

## License

The major part of the project is [Apache 2.0][apache-license-2] licensed.

Files deemed insignificant in terms of copyright such as configuration files are
licensed under the public domain "no rights reserved" [CC0] license.

The repositoy is [REUSE][reuse-home] compliant.


[PyMilter]: https://pythonhosted.org/pymilter/
[PpyMilter]: https://github.com/jmehnle/ppymilter
[python-libmilter]: https://github.com/crustymonkey/python-libmilter
[postfix-socketmap-table]: https://www.postfix.org/socketmap_table.5.html
[postfix-smtpd-policy-protocol]: https://www.postfix.org/SMTPD_POLICY_README.html#protocol
[pypolicyd-spf]: https://launchpad.net/pypolicyd-spf
[dmarc-rfc7489-sec31]: https://datatracker.ietf.org/doc/html/rfc7489#section-3.1
[opendkim-readme]: http://www.opendkim.org/opendkim-README
[sendmail-pmilter]: https://metacpan.org/pod/Sendmail::PMilter
[postfix-mta-sts-resolver]: https://github.com/Snawoot/postfix-mta-sts-resolver
[wikipedia-mta]: https://en.wikipedia.org/wiki/Message_transfer_agent
[postfix-home]: https://www.postfix.org/
[sendmail-org-home]: https://www.sendmail.org/
[sendmail-relnotes-kr-c-deprecation]: https://salsa.debian.org/debian/sendmail/-/blob/0ad6934dd77ca9ef1e2a64a9862ceb9b56a7d3f8/RELEASE_NOTES#L48-53
[examples-readme]: ./src/purepythonmilter/examples/README.md
[postfix-filter-readme]: https://www.postfix.org/FILTER_README.html
[indymilter]: https://gitlab.com/glts/indymilter
[andybalholm/milter]: https://github.com/andybalholm/milter
[andybalholm/grayland]: https://github.com/andybalholm/grayland
[emersion/go-milter]: https://github.com/emersion/go-milter
[phalaaxx/milter]: https://github.com/phalaaxx/milter
[phalaaxx/ratemilter]: https://github.com/phalaaxx/ratemilter
[phalaaxx/pf-milters]: https://github.com/phalaaxx/pf-milters
[mschneider82/milterclient]: https://github.com/mschneider82/milterclient
[Freeaqingme/ClueGetter]: https://github.com/Freeaqingme/ClueGetter
[nightcode/jmilter]: https://github.com/nightcode/jmilter
[sendmail-jilter]: http://sendmail-jilter.sourceforge.net/
[Atlantis-Software/milterjs]: https://github.com/Atlantis-Software/milterjs
[github-new-issue]: https://github.com/gertvdijk/purepythonmilter/issues/new/choose
[github-new-discussion]: https://github.com/gertvdijk/purepythonmilter/discussions/new
[github-ideas-feature-requests]: https://github.com/gertvdijk/purepythonmilter/discussions/categories/ideas-feature-requests
[spf-milter]: https://gitlab.com/glts/spf-milter
[python-libmilter-readme-note]: https://github.com/crustymonkey/python-libmilter/blob/9793148913232b726da692c7fd0ae2c3edec497c/README.md#no-longer-supporting
[CC0]: https://creativecommons.org/share-your-work/public-domain/cc0/
[apache-license-2]: https://www.apache.org/licenses/LICENSE-2.0
[reuse-home]: https://reuse.software/
[pep-427]: https://peps.python.org/pep-0427/
[pymilter-miltermodule-c]: https://github.com/sdgathman/pymilter/blob/master/miltermodule.c

[^sendmail-relnotes-kr-c-deprecation]: [Sendmail 8.71.1 Release notes][sendmail-relnotes-kr-c-deprecation]:

    > 2021/08/17
    >
    > Deprecation notice: due to compatibility problems with some third party code, we
    > plan to finally switch from K&R to ANSI C. If you are using sendmail on a system
    > which does not have a compiler for ANSI C contact us with details as soon as
    > possible so we can determine how to proceed.
