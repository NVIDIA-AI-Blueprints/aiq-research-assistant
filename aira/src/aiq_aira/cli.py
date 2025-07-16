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
import json

import click
import dotenv
import httpx

BOLD = "\033[1m"
BLUE = "\033[94m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


@click.group(name="aiq", invoke_without_command=True, no_args_is_help=True)
@click.pass_context
def run_cli(ctx: click.Context):

    dotenv.load_dotenv(override=True)


@run_cli.group(name="auth", invoke_without_command=True, no_args_is_help=True)
@click.option("--prod", is_flag=True, help="Use production auth endpoints")
@click.pass_context
def auth(ctx: click.Context, prod: bool = False):

    ctx.ensure_object(dict)
    ctx.obj["prod"] = prod


@auth.command()
@click.option("--force-login", is_flag=True, help="Force login to Starfleet")
@click.option("--force-refresh", is_flag=True, help="Force refresh of Starfleet credentials")
@click.pass_context
def starfleet(ctx: click.Context, force_login: bool, force_refresh: bool):

    from aiq_aira.functions.eci.eci_search_utils import starfleet_login

    async def _starfleet_login():
        async with httpx.AsyncClient() as client:
            await starfleet_login(client=client,
                                  prod=ctx.obj["prod"],
                                  force_login=force_login,
                                  force_refresh=force_refresh)

    asyncio.run(_starfleet_login())


@auth.command()
@click.option("--force-login", is_flag=True, help="Force login to SSA")
@click.pass_context
def ssa(ctx: click.Context, force_login: bool):

    from aiq_aira.functions.eci.eci_search_utils import ssa_login

    async def _ssa_login():
        async with httpx.AsyncClient() as client:
            await ssa_login(client=client, prod=ctx.obj["prod"], force_login=force_login)

    asyncio.run(_ssa_login())


@run_cli.command()
@click.option("--prod", is_flag=True, help="Use production ECI endpoints")
@click.option("--query", type=str, help="The query to make to the ECI")
@click.option("--data-sources", type=str, multiple=True, help="The data sources to use for the query")
@click.option("--max-snippet-size", type=int, default=1000, help="The maximum snippet size to use for the query")
@click.pass_context
def eci(ctx: click.Context, prod: bool, query: str, data_sources: list[str], max_snippet_size: int):

    from aiq_aira.functions.eci.eci_search import ECISearchRequest
    from aiq_aira.functions.eci.eci_search import eci_search_single

    async def _eci_request():
        async with httpx.AsyncClient() as client:

            request = ECISearchRequest(query=query,
                                       data_sources=data_sources,
                                       allow_login=True,
                                       max_snippet_size=max_snippet_size)

            while (True):
                result = await eci_search_single(client=client, prod=prod, request=request)

                print(f"{GREEN}Successfully made ECI request.{RESET}")
                print(json.dumps(result.model_dump(mode="json"), indent=2))

                if (result.has_more_results):
                    input("Additional results found. Press Enter to continue or Ctrl-C to exit...")

                    request.cursor = result.cursor

                else:
                    print(f"{GREEN}No more results found.{RESET}")
                    break

    asyncio.run(_eci_request())


if __name__ == "__main__":
    run_cli(auto_envvar_prefix='AIRA', show_default=True, prog_name="aira")
