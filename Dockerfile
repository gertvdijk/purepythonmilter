# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

# syntax=docker/dockerfile:1.3

ARG FROM_IMAGE

### Base stage ###
# https://github.com/hadolint/hadolint/issues/339
# hadolint ignore=DL3006
FROM $FROM_IMAGE as base

# https://github.com/hadolint/hadolint/issues/562
# hadolint ignore=DL3005
RUN apt-get update --quiet \
    && apt-get dist-upgrade --quiet --yes \
    && apt-get autoremove --quiet --yes \
    && rm -rf /var/lib/apt/lists

# Keep in sync with stage below.
RUN adduser \
      --system \
      --group \
      --uid 500 \
      --disabled-login \
      --disabled-password \
      --gecos "purepythonmilter,,," \
      --home /purepythonmilter \
      purepythonmilter

USER purepythonmilter:purepythonmilter
WORKDIR /purepythonmilter

# Silence warning from pip that local bin directory is not on PATH.
# Keep in sync with stage below.
RUN mkdir -p "${HOME}/.local/bin"
ENV PATH="/purepythonmilter/.local/bin:${PATH}"

### Build stage 1/2: dependencies ###
FROM base as builder-deps

USER root:root
# Install a specified version of pip & setuptools globally.
# Not in the user's site-packages, because we don't need it in there as dependency.
# Also, mount a Buildkit-cachable ~/.cache directory to speed up pip-installs.
# And therefore purposefully ignore DL3042.
# hadolint ignore=DL3042
RUN --mount=type=cache,target=/root/.cache \
    python -m pip install pip==23.0 setuptools==67.1.0 setuptools-scm[toml]==7.1.0
USER purepythonmilter:purepythonmilter

# Install dependencies (for 'examples' optional set) with pinned version manually.
# Mount a Buildkit-cachable ~/.cache directory to speed up pip-installs.
# And therefore purposefully ignore DL3042.
# hadolint ignore=DL3042
RUN --mount=type=cache,target=/purepythonmilter/.cache \
    python -m pip install --user \
        attrs==22.2.0 \
        click==8.1.3

### Build stage 2/2: the package itself ###
FROM builder-deps as builder

# Copy to a temp location, because pip with setuptools backends
# needs a writable source directory.
# https://pip.pypa.io/en/stable/cli/pip_install/#local-project-installs
RUN --mount=type=bind,source=/,target=/purepythonmilter/reporoot \
    cp -r /purepythonmilter/reporoot /tmp/reporootcopy
# By passing SETUPTOOLS_SCM_PRETEND_VERSION we eliminate the need for git here.
ARG SETUPTOOLS_SCM_PRETEND_VERSION
RUN python -m pip --no-cache-dir install --user '/tmp/reporootcopy[examples]'

# Verify that all packages are up-to-date (`pip list --outdated` should give no output),
# and do not cache (always run, except within the same minute).
ARG CACHEBUST_MINUTE
# Unfortunately, pip returns exit status 0 regardless of status.
# hadolint ignore=SC2028
RUN outdated=$(python -m pip list --no-cache-dir --outdated 2>&1) \
    && [ -z "$outdated" ] \
    || (echo "'pip list --outdated' @ ${CACHEBUST_MINUTE}:\n${outdated}"; exit 1)

### Final stage ###
FROM base

# Dependencies only (separate as stable layer).
COPY --from=builder-deps /purepythonmilter/.local .local
# purepythonmilter itself.
COPY --from=builder /purepythonmilter/.local .local
ENV PATH="/purepythonmilter/.local/bin:${PATH}"

ENV PUREPYTHONMILTER_BIND_HOST=0.0.0.0

# If you want to run a specific example by default, specify like this:
# CMD ["python", "-m", "purepythonmilter.examples.debug_log_all", "--log-level=DEBUG"]
#
# Or else, specify the command at run time.
