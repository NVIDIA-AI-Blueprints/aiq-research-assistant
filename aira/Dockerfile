# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

FROM nvcr.io/nvidia/base/ubuntu:jammy-20250415.1


# Install uv package manager
# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

RUN uv python install 3.12

# Copy the local build context (your project files) into the container's /app directory
COPY ./aira/entrypoint.sh /entrypoint.sh
COPY ./aira/. /app


RUN uv venv --python-preference managed
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_AIQ_AIRA="0.0.0"

# Use uv to install Python dependencies 
RUN uv pip install /app 

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]