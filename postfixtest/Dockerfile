# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: CC0-1.0

# syntax=docker/dockerfile:1.3
ARG FROM_IMAGE=debian:bullseye
FROM $FROM_IMAGE

COPY files/apt-install-clean.sh /usr/local/bin/apt-install-clean

RUN apt-install-clean \
        'postfix=3.*' \
    && cp -a /etc/postfix /etc/postfix-default

COPY files/entrypoint.sh /usr/local/sbin/postfix-entrypoint.sh

# Docker default network, IP of host.
ENV POSTFIX_MILTER_HOST=172.17.0.1
ENV POSTFIX_MILTER_PORT=9000

ENTRYPOINT ["/usr/local/sbin/postfix-entrypoint.sh"]
