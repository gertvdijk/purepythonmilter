# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: CC0-1.0

DOCKER_BUILD_OPTS?=
FROM_IMAGE=debian:bullseye
CONTAINER_NAME=purepythonmilter-postfixtest

.NOTPARALLEL:

.PHONY: default
default: build-postfix run-postfix

.PHONY: build-postfix
build-postfix:
	docker pull "$(FROM_IMAGE)"
	docker build \
	$(DOCKER_BUILD_OPTS) \
	--build-arg=FROM_IMAGE="$(FROM_IMAGE)" \
	-t purepythonmilter-postfix:latest \
	.

.PHONY: run-postfix
run-postfix:
	docker run \
	    --name $(CONTAINER_NAME) \
		--rm \
		--interactive \
		--tty \
		purepythonmilter-postfix:latest

.PHONY: shell
shell:
	docker run \
	    --name $(CONTAINER_NAME) \
		--rm \
		--interactive \
		--tty \
		--entrypoint /bin/bash \
		purepythonmilter-postfix:latest

.PHONY: get-ipv4
get-ipv4:
	docker inspect -f \
	    '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
	    $(CONTAINER_NAME)
