import asyncio
import base64
import json
import os
import socket
import time
import uuid
import webbrowser
from io import StringIO

import appdirs
import click
import dotenv
import httpx
import jwt
from httpx._exceptions import HTTPStatusError
from pydantic import BaseModel

BOLD = "\033[1m"
BLUE = "\033[94m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

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


class SavedCredentials(BaseModel):
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


def to_local_time_str(timestamp: float):
    return time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(timestamp))


def custom_raise_for_status(response: httpx.Response):

    if response.is_success:
        return

    message = f"HTTP Error. Code: {response.status_code}, Reason: {response.reason_phrase}, URL: {response.url}"

    if response.text:
        message += f", Text:\n{response.text}"

    raise HTTPStatusError(message, request=response.request, response=response)


async def starfleet_login_flow(client: httpx.AsyncClient) -> SavedCredentials:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    params = {
        "client_id": "hcp8mQYPXzgxbZ9fvlSOZeAUf-Y4S_JAt_pzG0PPjTs",
        "device_id": get_mac_address(),
        "display_name": socket.gethostname(),
        "scope": ["openid", "email", "profile"],
    }

    response = await client.post("https://stg.login.nvidia.com/device/authorize", headers=headers, data=params)

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
            "client_id": "hcp8mQYPXzgxbZ9fvlSOZeAUf-Y4S_JAt_pzG0PPjTs",
        }

        response = await client.post("https://stg.login.nvidia.com/token", headers=headers, data=params)

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

    response = await client.get("https://stg.login.nvidia.com/client_token", headers=headers)

    custom_raise_for_status(response)

    client_token_response = ClientTokenResponse.model_validate(response.json())

    client_token_expires_at = time.time() + client_token_response.expires_in

    saved_credentials = SavedCredentials(id_token=token_response.id_token,
                                         access_token=token_response.access_token,
                                         token_type=token_response.token_type,
                                         id_token_expires_at=id_token_expires_at,
                                         client_token=client_token_response.client_token,
                                         client_token_expires_at=client_token_expires_at)

    return saved_credentials


async def starfleet_refresh_flow(client: httpx.AsyncClient, saved_credentials: SavedCredentials) -> SavedCredentials:
    # Decode the id_token to get the sub
    decoded_id_token = jwt.decode(saved_credentials.id_token, options={"verify_signature": False})

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    params = {
        "grant_type": "urn:ietf:params:oauth:grant-type:client_token",
        "client_id": "hcp8mQYPXzgxbZ9fvlSOZeAUf-Y4S_JAt_pzG0PPjTs",
        "client_token": saved_credentials.client_token,
        "sub": decoded_id_token["sub"],
    }

    response = await client.post("https://stg.login.nvidia.com/token", headers=headers, data=params)

    custom_raise_for_status(response)

    token_response = TokenResponse.model_validate(response.json())

    saved_credentials = SavedCredentials(id_token=saved_credentials.id_token,
                                         access_token=token_response.access_token,
                                         token_type=token_response.token_type,
                                         id_token_expires_at=time.time() + token_response.expires_in,
                                         client_token=saved_credentials.client_token,
                                         client_token_expires_at=saved_credentials.client_token_expires_at)

    return saved_credentials


async def starfleet_login(force_login: bool = False, force_refresh: bool = False):

    # First, check if we have saved credentials
    app_data_dir = appdirs.user_cache_dir(appauthor="NVIDIA", appname="nvidia-aiq-util")
    credentials_file = os.path.join(app_data_dir, "starfleet-credentials.json")

    saved_credentials: SavedCredentials | None = None

    async with httpx.AsyncClient() as client:
        try:
            if os.path.exists(credentials_file) and not force_login:
                with open(credentials_file, "r", encoding="utf-8") as f:
                    saved_credentials = SavedCredentials.model_validate_json(f.read())

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

                    saved_credentials = await starfleet_refresh_flow(client, saved_credentials)

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
            saved_credentials = await starfleet_login_flow(client)

        # Save both the token and the client token to a file on the machine in the default appdata directory
        os.makedirs(app_data_dir, exist_ok=True)

        with open(credentials_file, "w", encoding="utf-8") as f:
            f.write(saved_credentials.model_dump_json())

        print(f"{GREEN}Successfully logged in to Starfleet!{RESET}")
        print(saved_credentials.print_info())
        print(f"Starfleet Credentials saved to {credentials_file}")

    return saved_credentials


async def ssa_login_flow(client: httpx.AsyncClient, eci_endpoint: str) -> SSASavedCredentials:

    client_id = os.getenv("AIQ_SSA_CLIENT_ID")
    client_secret = os.getenv("AIQ_SSA_CLIENT_SECRET")

    if (not client_id):
        raise Exception("AIQ_SSA_CLIENT_ID environment variable not set")

    if (not client_secret):
        raise Exception("AIQ_SSA_CLIENT_SECRET environment variable not set")

    response = await client.get(f"{eci_endpoint}/.well-known/oauth-authorization-server")

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


async def ssa_login(force_login: bool, eci_endpoint: str):

    app_data_dir = appdirs.user_cache_dir(appauthor="NVIDIA", appname="nvidia-aiq-util")
    credentials_file = os.path.join(app_data_dir, "ssa-credentials.json")

    saved_credentials: SSASavedCredentials | None = None

    async with httpx.AsyncClient() as client:
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
            saved_credentials = await ssa_login_flow(client, eci_endpoint)

        # Save both the token and the client token to a file on the machine in the default appdata directory
        os.makedirs(app_data_dir, exist_ok=True)

        with open(credentials_file, "w", encoding="utf-8") as f:
            f.write(saved_credentials.model_dump_json())

        print(f"{GREEN}Successfully logged in to SSA!{RESET}")
        print(saved_credentials.print_info())
        print(f"SSA Credentials saved to {credentials_file}")

    return saved_credentials


async def get_starfleet_token() -> str:

    token = os.getenv("AIQ_STARFLEET_TOKEN", None)

    if (token is None):
        starfleet_saved_credentials = await starfleet_login()

        token = starfleet_saved_credentials.id_token

    return token


async def get_ssa_token(eci_endpoint: str) -> str:

    token = os.getenv("AIQ_SSA_TOKEN", None)

    if (token is None):
        ssa_saved_credentials = await ssa_login(force_login=False, eci_endpoint=eci_endpoint)

        token = ssa_saved_credentials.access_token

    return token


async def eci_request(eci_endpoint: str, query: str):

    async with httpx.AsyncClient() as client:

        # First, get the saved credentials
        starfleet_token = await get_starfleet_token()
        ssa_token = await get_ssa_token(eci_endpoint=eci_endpoint)

        # Now, make the request
        headers = {
            "Authorization": f"Bearer {ssa_token}",
            "Nv-Actor-Token": starfleet_token,
            "Content-Type": "application/json",
        }

        cursor = None

        while (True):
            payload = {
                "query": query,
                "pageSize": 10,
                # "requestOptions": {
                #     "datasourcesFilter": ["NVBUGS"]
                # },
            }

            if (cursor is not None):
                payload["cursor"] = cursor

            response = await client.post(f"{eci_endpoint}/v1/content/search", headers=headers, json=payload)
            
            custom_raise_for_status(response)

            response_json = response.json()

            return response_json



@click.group(name="aiq", invoke_without_command=True, no_args_is_help=True)
def cli():

    dotenv.load_dotenv()


@cli.command()
@click.option("--force-login", is_flag=True, help="Force login to Starfleet")
@click.option("--force-refresh", is_flag=True, help="Force refresh of Starfleet credentials")
def starfleet(force_login: bool, force_refresh: bool):
    asyncio.run(starfleet_login(force_login=force_login, force_refresh=force_refresh))


@cli.command()
@click.option("--force-login", is_flag=True, help="Force login to SSA")
@click.option("--eci-endpoint",
              type=str,
              default="https://enterprise-content-intelligence-stg.nvidia.com",
              help="The endpoint to make the request to")
def ssa(force_login: bool, eci_endpoint: str):
    asyncio.run(ssa_login(force_login=force_login, eci_endpoint=eci_endpoint))


@cli.command()
@click.option("--eci-endpoint",
              type=str,
              default="https://enterprise-content-intelligence-stg.nvidia.com",
              help="The endpoint to make the request to")
@click.option("--query", type=str, help="The query to make to the ECI")
def eci(query: str, eci_endpoint: str):
    asyncio.run(eci_request(eci_endpoint=eci_endpoint, query=query))


if __name__ == "__main__":
    cli(auto_envvar_prefix='AIQ', show_default=True, prog_name="aiq-util")
