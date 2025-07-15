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

import asyncio
import base64
import logging
import os
import socket
import time
import uuid
import webbrowser
from io import StringIO

import appdirs
import httpx
import jwt
from aiq.builder.context import AIQContext
from pydantic import BaseModel

from aiq_aira.utils import BLUE
from aiq_aira.utils import BOLD
from aiq_aira.utils import GREEN
from aiq_aira.utils import RED
from aiq_aira.utils import RESET
from aiq_aira.utils import YELLOW
from aiq_aira.utils import custom_raise_for_status
from aiq_aira.utils import to_local_time_str

logger = logging.getLogger(__name__)

LOGIN_MESSAGE = """
! First, copy the following code to your clipboard: {user_code}
Press Enter to open {verification_uri} in your browser...
"""


class DeviceAuthResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class TokenResponse(BaseModel):
    id_token: str
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
    client_token: str | None = None


class ClientTokenResponse(BaseModel):
    client_token: str
    expires_in: int


class StarfleetSavedCredentials(BaseModel):
    id_token: str
    access_token: str
    token_type: str
    id_token_expires_at: float
    client_token: str
    client_token_expires_at: float

    def print_info(self):
        ss = StringIO()

        ss.write(f"{BOLD}{BLUE}Current Starfleet Credentials:{RESET}\n")
        ss.write(f"{YELLOW} - ID token: {RESET}{self.id_token}\n")
        ss.write(f"{YELLOW}   Expiration: {RESET}{to_local_time_str(self.id_token_expires_at)}\n")
        ss.write(f"{YELLOW} - Access token: {RESET}{self.access_token}\n")
        ss.write(f"{YELLOW}   Token type: {RESET}{self.token_type}\n")
        ss.write(f"{YELLOW} - Client token: {RESET}{self.client_token}\n")
        ss.write(f"{YELLOW}   Expiration: {RESET}{to_local_time_str(self.client_token_expires_at)}")

        return ss.getvalue()


class OauthServerInfo(BaseModel):
    issuer: str
    token_endpoint: str
    jwks_uri: str
    response_types_supported: list[str]
    scopes_supported: list[str]


class SSATokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str


class SSASavedCredentials(BaseModel):
    access_token: str
    token_type: str
    expires_at: float
    scope: list[str]

    def print_info(self):

        ss = StringIO()

        ss.write(f"{BOLD}{BLUE}Current SSA Credentials:{RESET}\n")
        ss.write(f"{YELLOW} - Access token: {RESET}{self.access_token}\n")
        ss.write(f"{YELLOW} - Token type: {RESET}{self.token_type}\n")
        ss.write(f"{YELLOW} - Expires at: {RESET}{to_local_time_str(self.expires_at)}\n")
        ss.write(f"{YELLOW} - Scope: {RESET}{self.scope}")

        return ss.getvalue()


def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(['{:02x}'.format((mac >> i) & 0xff) for i in range(0, 48, 8)][::-1])


async def starfleet_login_flow(*, client: httpx.AsyncClient, prod: bool = False) -> StarfleetSavedCredentials:

    client_id = os.getenv("AIQ_STARFLEET_CLIENT_ID")

    if (not client_id):
        raise Exception("AIQ_STARFLEET_CLIENT_ID environment variable not set")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    params = {
        "client_id": client_id,
        "device_id": get_mac_address(),
        "display_name": socket.gethostname(),
        "scope": ["openid", "email", "profile"],
    }

    response = await client.post(f"https://{'stg.' if not prod else ''}login.nvidia.com/device/authorize",
                                 headers=headers,
                                 data=params)

    custom_raise_for_status(response)

    device_auth_response = DeviceAuthResponse.model_validate(response.json())

    input(
        LOGIN_MESSAGE.format(user_code=device_auth_response.user_code,
                             verification_uri=device_auth_response.verification_uri))

    # Now open the verification_uri in the browser
    webbrowser.open(device_auth_response.verification_uri)

    while True:
        await asyncio.sleep(device_auth_response.interval)

        params = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_auth_response.device_code,
            "client_id": client_id,
        }

        response = await client.post(f"https://{'stg.' if not prod else ''}login.nvidia.com/token",
                                     headers=headers,
                                     data=params)

        if (response.status_code == 400):
            if (response.json().get("error") == "authorization_pending"):
                continue
            else:
                raise Exception(response.text)
        else:
            custom_raise_for_status(response)

        # Must have been a success
        token_response = TokenResponse.model_validate(response.json())

        id_token_expires_at = time.time() + token_response.expires_in

        break

    # Now get the client_token to support refreshing
    headers = {
        "Authorization": f"Bearer {token_response.access_token}",
    }

    response = await client.get(f"https://{'stg.' if not prod else ''}login.nvidia.com/client_token", headers=headers)

    custom_raise_for_status(response)

    client_token_response = ClientTokenResponse.model_validate(response.json())

    client_token_expires_at = time.time() + client_token_response.expires_in

    saved_credentials = StarfleetSavedCredentials(id_token=token_response.id_token,
                                                  access_token=token_response.access_token,
                                                  token_type=token_response.token_type,
                                                  id_token_expires_at=id_token_expires_at,
                                                  client_token=client_token_response.client_token,
                                                  client_token_expires_at=client_token_expires_at)

    return saved_credentials


async def starfleet_refresh_flow(*,
                                 client: httpx.AsyncClient,
                                 saved_credentials: StarfleetSavedCredentials,
                                 prod: bool = False) -> StarfleetSavedCredentials:
    # Decode the id_token to get the sub
    decoded_id_token = jwt.decode(saved_credentials.id_token, options={"verify_signature": False})

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    client_id = os.getenv("AIQ_STARFLEET_CLIENT_ID")

    if (not client_id):
        raise Exception("AIQ_STARFLEET_CLIENT_ID environment variable not set")

    params = {
        "grant_type": "urn:ietf:params:oauth:grant-type:client_token",
        "client_id": client_id,
        "client_token": saved_credentials.client_token,
        "sub": decoded_id_token["sub"],
    }

    response = await client.post(f"https://{'stg.' if not prod else ''}login.nvidia.com/token",
                                 headers=headers,
                                 data=params)

    custom_raise_for_status(response)

    token_response = TokenResponse.model_validate(response.json())

    saved_credentials = StarfleetSavedCredentials(id_token=token_response.id_token,
                                                  access_token=token_response.access_token,
                                                  token_type=token_response.token_type,
                                                  id_token_expires_at=time.time() + token_response.expires_in,
                                                  client_token=saved_credentials.client_token,
                                                  client_token_expires_at=saved_credentials.client_token_expires_at)

    return saved_credentials


async def starfleet_login(*, prod: bool = False, force_login: bool = False, force_refresh: bool = False):

    # First, check if we have saved credentials
    app_data_dir = appdirs.user_cache_dir(appauthor="NVIDIA", appname="nvidia-aiq-util")
    credentials_file = os.path.join(app_data_dir, f"starfleet-credentials{'-stg' if not prod else '-prod'}.json")

    saved_credentials: StarfleetSavedCredentials | None = None

    async with httpx.AsyncClient() as client:
        try:
            if os.path.exists(credentials_file) and not force_login:
                with open(credentials_file, "r", encoding="utf-8") as f:
                    saved_credentials = StarfleetSavedCredentials.model_validate_json(f.read())

                # Check if the token has expired (within 1 minute)
                if saved_credentials.id_token_expires_at > time.time() - 60 and not force_refresh:
                    # Token is still valid, so we can use it. Print the expiration time in a human readable format
                    print(f"{GREEN}Existing Starfleet Credentials found and still valid.{RESET}")
                    print(saved_credentials.print_info())

                    return saved_credentials
                elif saved_credentials.client_token_expires_at > time.time() - 60:
                    # ID token has expired, but client token is still valid
                    print(
                        f"{YELLOW}Existing Starfleet Credentials found but ID token has expired. Refreshing...{RESET}")

                    saved_credentials = await starfleet_refresh_flow(client=client,
                                                                     saved_credentials=saved_credentials,
                                                                     prod=prod)

                else:
                    # Both tokens have expired, so we need to refresh them
                    print(
                        f"{RED}Existing Starfleet Credentials found but both tokens have expired. Logging in again...{RESET}"
                    )
                    os.remove(credentials_file)

                    saved_credentials = None

        except Exception as e:
            print(f"{RED}Error trying to load Starfleet Credentials: {e}{RESET}")
            print(f"{YELLOW}Running Starfleet login process...{RESET}")

            saved_credentials = None

        if (not saved_credentials):
            saved_credentials = await starfleet_login_flow(client=client, prod=prod)

        # Save both the token and the client token to a file on the machine in the default appdata directory
        os.makedirs(app_data_dir, exist_ok=True)

        with open(credentials_file, "w", encoding="utf-8") as f:
            f.write(saved_credentials.model_dump_json())

        print(f"{GREEN}Successfully logged in to Starfleet!{RESET}")
        print(saved_credentials.print_info())
        print(f"Starfleet Credentials saved to {credentials_file}")

    return saved_credentials


async def ssa_login_flow(*, client: httpx.AsyncClient, prod: bool = False) -> SSASavedCredentials:

    client_id = os.getenv("AIQ_SSA_CLIENT_ID")
    client_secret = os.getenv("AIQ_SSA_CLIENT_SECRET")

    if (not client_id):
        raise Exception("AIQ_SSA_CLIENT_ID environment variable not set")

    if (not client_secret):
        raise Exception("AIQ_SSA_CLIENT_SECRET environment variable not set")

    response = await client.get(
        f"https://enterprise-content-intelligence{'-stg' if not prod else ''}.nvidia.com/.well-known/oauth-authorization-server"
    )

    custom_raise_for_status(response)

    oauth_server_info = OauthServerInfo.model_validate(response.json())

    # Convert the service_id to a base64 encoded string
    serialized_client_creds = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {serialized_client_creds}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    params = {
        "grant_type":
            "client_credentials",
        "scope":
            " ".join([
                "content:classify",
                "content:summarize",
                "content:search",
                "content:retrieve",
                "content:retrieve_metadata",
                "account:verify_access"
            ]),
    }

    response = await client.post(oauth_server_info.token_endpoint, headers=headers, data=params)

    custom_raise_for_status(response)

    token_response = SSATokenResponse.model_validate(response.json())

    ssa_saved_credentials = SSASavedCredentials(access_token=token_response.access_token,
                                                token_type=token_response.token_type,
                                                expires_at=time.time() + token_response.expires_in,
                                                scope=token_response.scope.split(" "))

    return ssa_saved_credentials


async def ssa_login(*, client: httpx.AsyncClient, prod: bool = False, force_login: bool = False):

    app_data_dir = appdirs.user_cache_dir(appauthor="NVIDIA", appname="nvidia-aiq-util")
    credentials_file = os.path.join(app_data_dir, f"ssa-credentials{'-stg' if not prod else '-prod'}.json")

    saved_credentials: SSASavedCredentials | None = None

    try:
        if os.path.exists(credentials_file) and not force_login:
            with open(credentials_file, "r", encoding="utf-8") as f:
                saved_credentials = SSASavedCredentials.model_validate_json(f.read())

            # Check if the token has expired (within 1 minute)
            if saved_credentials.expires_at > time.time() - 60:
                # Token is still valid, so we can use it. Print the expiration time in a human readable format
                print(f"{GREEN}Existing SSA Credentials found and still valid.{RESET}")
                print(saved_credentials.print_info())

                return saved_credentials

            else:
                # Both tokens have expired, so we need to refresh them
                print(f"{RED}Existing SSA Credentials found but have expired. Logging in again...{RESET}")
                os.remove(credentials_file)

                saved_credentials = None

    except Exception as e:
        print(f"{RED}Error trying to load SSA Credentials: {e}{RESET}")
        print(f"{YELLOW}Running SSA login process...{RESET}")

        saved_credentials = None

    if (not saved_credentials):
        saved_credentials = await ssa_login_flow(client=client, prod=prod)

    # Save both the token and the client token to a file on the machine in the default appdata directory
    os.makedirs(app_data_dir, exist_ok=True)

    with open(credentials_file, "w", encoding="utf-8") as f:
        f.write(saved_credentials.model_dump_json())

    print(f"{GREEN}Successfully logged in to SSA!{RESET}")
    print(saved_credentials.print_info())
    print(f"SSA Credentials saved to {credentials_file}")

    return saved_credentials


async def get_starfleet_token(*, prod: bool = False, allow_login: bool = False) -> str:

    # First, check if we have the token in the auth header
    headers = AIQContext.get().metadata.headers

    if (headers is not None):
        auth_header = headers.get("Authorization", None)
    else:
        auth_header = None

    if (auth_header is not None):
        return auth_header

    # Next, check if we have the token in the environment variable
    token = os.getenv("AIQ_STARFLEET_TOKEN", None)

    if (token is not None):
        return token

    if (allow_login):
        starfleet_saved_credentials = await starfleet_login(prod=prod, force_login=False)

        return starfleet_saved_credentials.id_token

    raise ValueError(
        "No Starfleet token found. Set the Starfleet token in the Authorization header or environment variable `AIQ_STARFLEET_TOKEN`"
    )


async def get_ssa_token(*, client: httpx.AsyncClient, prod: bool = False) -> str:

    token = os.getenv("AIQ_SSA_TOKEN", None)

    if (token is None):
        ssa_saved_credentials = await ssa_login(client=client, prod=prod, force_login=False)

        token = ssa_saved_credentials.access_token

    return token
