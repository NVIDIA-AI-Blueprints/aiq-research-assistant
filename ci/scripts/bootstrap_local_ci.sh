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

if [[ "${USE_HOST_GIT}" == "1" ]]; then   
    cd /aiq-bp-internal
    git config --global --add safe.directory /aiq-bp-internal

else
    git clone ${GIT_URL} aiq-bp-internal
    cd aiq-bp-internal/
    git remote add upstream ${GIT_UPSTREAM_URL}
    git fetch upstream
    git checkout trunk
    git checkout ${GIT_BRANCH}
    git pull
    git checkout ${GIT_COMMIT}
    git fetch --all --tags

    export CURRENT_BRANCH=${GIT_BRANCH}
    export COMMIT_SHA=${GIT_COMMIT}
fi

export WORKSPACE=$(pwd)
export LOCAL_CI=1
export WORKSPACE_TMP="${LOCAL_CI_TMP}/local_ci_workspace"
export UV_CACHE_DIR="${LOCAL_CI_TMP}/cache/uv"
export PRE_COMMIT_HOME="${LOCAL_CI_TMP}/cache/pre_commit"
export XDG_CACHE_HOME="${LOCAL_CI_TMP}/cache/xdg"
export BUILD_AIQ_COMPAT="true"
mkdir -p ${UV_CACHE_DIR}

pip install uv
uv venv --seed ${WORKSPACE_TMP}/.venv
source ${WORKSPACE_TMP}/.venv/bin/activate
uv pip install -e "./aira[dev]"

GITLAB_SCRIPT_DIR="${WORKSPACE}/ci/scripts/gitlab"


if [[ "${STAGE}" != "bash" ]]; then

    CI_SCRIPT="${GITLAB_SCRIPT_DIR}/${STAGE}.sh"

    ${CI_SCRIPT}
fi
