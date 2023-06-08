# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: CC0-1.0

SHELL=/bin/bash -o pipefail

DOCKER_BUILD_OPTS ?=
PYTHON_PKG_VERSION ?= $(shell python -m setuptools_scm)
# Docker tags with '+' are not supported.
IMAGE_TAG ?= $(shell echo "$(PYTHON_PKG_VERSION)" | tr + _)
IMAGE_NAME := purepythonmilter
# python:3.10.12-slim-bullseye linux/amd64 @ 2023-06-08
# https://hub.docker.com/_/python/tags?page=1&name=3.10-slim-bullseye
FROM_IMAGE := python@sha256:c451f80b867635bab3c4db35b272f54cfa3923922cac7eebe2cdf4bb301fb848

CACHEBUST_MINUTE := $(shell date '+%Y-%m-%d %H:%M')

.NOTPARALLEL:

.PHONY: default
default: build push

.PHONY: guard-*
guard-%:
	@ if [ "$(${*})" = "" ]; then \
		echo "Variable $* not set"; \
		exit 1; \
	fi

.PHONY: build
build: guard-IMAGE_REGISTRY
	DOCKER_BUILDKIT=1 \
	docker build $(DOCKER_BUILD_OPTS) \
	  -t "$(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)" \
	  --build-arg="FROM_IMAGE=$(FROM_IMAGE)" \
	  --build-arg="SETUPTOOLS_SCM_PRETEND_VERSION=$(PYTHON_PKG_VERSION)" \
	  --build-arg="CACHEBUST_MINUTE=$(CACHEBUST_MINUTE)" \
	  .

.PHONY: push
push: guard-IMAGE_REGISTRY
	docker push "$(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)"
