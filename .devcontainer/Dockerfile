# syntax=docker/dockerfile:1
FROM python:3.12-slim

# uv (pinned to match the production Dockerfile)
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

# System packages useful inside a dev container:
#   git/openssh-client  — VS Code source control + git over SSH
#   build-essential     — building wheels that lack manylinux binaries
#   curl/ca-certificates — fetching tools, healthchecks
#   postgresql-client   — `psql` against the compose postgres service
#   redis-tools         — `redis-cli` against the compose redis service
#   sudo                — passwordless sudo for the vscode user
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        build-essential \
        curl \
        ca-certificates \
        postgresql-client \
        redis-tools \
        sudo \
    && rm -rf /var/lib/apt/lists/*

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/workspace/.venv/bin:$PATH"

WORKDIR /workspace
USER $USERNAME
