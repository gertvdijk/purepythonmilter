#!/bin/bash -e

# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: CC0-1.0

echo unconfigured.docker.container.local > /etc/mailname

# Copy the /etc/services file in the spool/queue directory as Postfix expects
# them to be there. See also
# https://serverfault.com/a/655127
mkdir -p /var/spool/postfix/etc
cp /etc/services /var/spool/postfix/etc/services
# Same goes for the trusted CA certs bundle. Still needs a configuration option
# smtp_tls_CAfile to point to it.
mkdir -p /var/spool/postfix/etc/ssl/certs/
cp /etc/ssl/certs/ca-certificates.crt /var/spool/postfix/etc/ssl/certs/ca-certificates.crt
# Also copy the resolv.conf, nsswitch.conf files along with the NSS shared
# libraries to the spool/queue directory as Postfix won't be able to resolve
# hostnames otherwise.
# See also https://askubuntu.com/a/155937
cp /etc/resolv.conf /etc/nsswitch.conf /var/spool/postfix/etc/
mkdir -p /var/spool/postfix/lib/x86_64-linux-gnu
cp /lib/x86_64-linux-gnu/libnss_* /var/spool/postfix/lib/x86_64-linux-gnu

postconf maillog_file=/dev/stdout

# Rely on the Postfix 3.4+ default master.cf containing the line
# 'postlog   unix-dgram [...]'

postconf "smtpd_milters=inet:${POSTFIX_MILTER_HOST}:${POSTFIX_MILTER_PORT}"

# Default timeout of 30s for a milter connection and that's rather long when developing.
postconf "milter_command_timeout=2s"
postconf "milter_content_timeout=2s"

# Accept mail for domain test.local as if it's a real mail server.
postconf "relay_domains=test.local"
# In order to actually queue mails for this imaginary (non-existant) domain, enable a
# transport for it which is unreachable. E.g.:
# postconf "transport_maps=inline:{test.local=[172.17.0.1]}"

# Specify your client IP/network here if you want more debugging from Postfix for
# connections made from these IPs. Very useful to debug the milter protocol
# implementation too.
# postconf "debug_peer_list=172.17.0.0/16"

exec /usr/sbin/postfix start-fg "$@"
