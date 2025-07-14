#!/bin/bash
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

set -e

GITLAB_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

source ${GITLAB_SCRIPT_DIR}/common.sh

if [[ "${LOCAL_CI}" == "1" ]]; then
  apt-get update
  apt-get install -y --no-install-recommends lsb-release
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update

  # Packages are listed alphabetically
  apt-get install -y --no-install-recommends \
          docker-buildx-plugin \
          docker-ce \
          docker-ce-cli \
          docker-compose-plugin
fi

GIT_TAG=$(get_git_tag)
IMAGE_NAME="nvcr.io/nvstaging/blueprint/aira-backend:${GIT_TAG}"
echo "Building container '${IMAGE_NAME}'"
docker build -f aira/Dockerfile -t "${IMAGE_NAME}" .

# Ensure we clean up even if the push fails
set +e

if [[ "${CI_CRON_NIGHTLY}" == "1" ||  "${CI_COMMIT_BRANCH}" == "staging" ]]; then
  docker login --username '$oauthtoken' --password "${NGC_API_KEY}" nvcr.io
  echo "Pushing image ${IMAGE_NAME}"
  docker push "${IMAGE_NAME}"
fi


if [[ "${KEEP_IMAGE}" == "1" ]]; then
  echo "Keeping image ${IMAGE_NAME}"
else
  echo "Removing image ${IMAGE_NAME}"
  docker image rm "${IMAGE_NAME}"
fi