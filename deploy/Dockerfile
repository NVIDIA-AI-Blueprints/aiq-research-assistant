# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /build

# Copy the source code
COPY ./pyproject.toml /build/pyproject.toml
COPY ./aira/ /build/aira/

# Build the package. Mount .git to get the version from the git tag
RUN --mount=source=.git,target=.git,type=bind \
   uv build --directory /build


######## Final Stage #########
FROM nvcr.io/nvidia/base/ubuntu:jammy-20250619

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install uv package manager
# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /app

# Install python 3.12 as the default python version
RUN uv python install 3.12
RUN uv venv --python-preference managed --seed

# Copy the local build context (your project files) into the container's /app directory
COPY ./deploy/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

# Copy the built package into the container's /app directory
RUN --mount=from=builder,source=/build,target=/build,type=bind \
    --mount=type=cache,target=/root/.cache/uv \
   uv pip install /build/dist/aiq_aira-*.whl

# Only copy the configs directory. The rest of the code is copied in the install
COPY ./configs/* /app/configs/

# Uncomment if we want to use the CMD instead of the entrypoint
# CMD ["uv", "run","aiq", "serve", "--config_file", "/app/configs/config.yml", "--host", "0.0.0.0", "--port", "3838"]

CMD ["/entrypoint.sh"]
