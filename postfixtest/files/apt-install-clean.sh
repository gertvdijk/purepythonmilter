#!/bin/sh -ex

# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: CC0-1.0

apt-get update

if [ "$1" = "--dist-upgrade" ]; then
    apt-get dist-upgrade -y
    shift
fi

# Relying on APT configuration that --no-install-recommends is not necessary.
apt-get install -y "$@"

# Relying on APT configuration that apt-get clean is not necessary.

# APT lists are not removed automatically.
rm -rf /var/lib/apt/lists/*
