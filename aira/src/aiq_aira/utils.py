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
import logging
import re
import time

import httpx
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Colors for logging
BOLD = "\033[1m"
BLUE = "\033[94m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


async def async_gen(num_loops: int):
    """
    Utility for retry loops or chunked iterations.
    """
    for i in range(num_loops):
        yield i
        await asyncio.sleep(0.0)


def to_local_time_str(timestamp: float):
    return time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(timestamp))


def custom_raise_for_status(response: httpx.Response):
    """
    Custom raise for status for httpx responses which provide a more detailed error message including any
    response text.
    """

    if response.is_success:
        return

    message = f"HTTP Error. Code: {response.status_code}, Reason: {response.reason_phrase}, URL: {response.url}"

    if response.text:
        message += f", Text:\n{response.text}"

    raise httpx.HTTPStatusError(message, request=response.request, response=response)


def update_system_prompt(system_prompt: str, llm: ChatOpenAI):
    """
    Update the system prompt for the LLM to enable reasoning if the model supports it
    """

    if hasattr(llm, "model") and "nemotron" in llm.model:
        system_prompt = "detailed thinking on"

    if hasattr(llm, "model_name") and "nemotron" in llm.model_name:
        system_prompt = "detailed thinking on"

    return system_prompt


def get_domain(url: str):
    """
    Extract the domain from a URL.
    """
    domain = url.split("/")[2]
    return domain.replace("www.", "") if domain.startswith("www.") else domain


async def dummy():
    """
    A do-nothing async function for placeholders.
    """
    return None


def format_sources(sources: str, source_num_start: int | None = None) -> str:
    """
    Format the sources into nicer looking markdown.
    """
    try:
        # Split sources into individual entries
        source_entries = re.split(r'(?=---\nQUERY:)', sources)
        formatted_sources = []
        src_count = 1
        if source_num_start is not None:
            src_count = source_num_start

        for idx, entry in enumerate(source_entries):
            if not entry.strip():
                continue

            # Split into query, answer, and citations using a more precise pattern
            # This pattern looks for newlines followed by QUERY:, ANSWER:, or CITATION(S):
            # but only if they're not preceded by a pipe (|) character (markdown table)
            src_parts = re.split(r'(?<!\|)\n(?=QUERY:|ANSWER:|CITATION(?:S)?:)', entry.strip())

            if len(src_parts) >= 4:
                source_num = src_count
                # Remove the prefix from each part
                query = re.sub(r'^QUERY:', '', src_parts[1]).strip()
                answer = re.sub(r'^ANSWER:', '', src_parts[2]).strip()

                # Handle multiple citations
                citations = ''.join(src_parts[3:])

                formatted_entry = f"""
---
**Source** {source_num}

**Query:** {query}

**Answer:**
{answer}

{citations}
"""
                formatted_sources.append(formatted_entry)
                src_count += 1
            else:
                logger.info(f"Failed to clean up {entry} because it failed to parse")
                formatted_sources.append(entry)
                src_count += 1

        # Combine main content with formatted sources
        return "\n".join(formatted_sources)
    except Exception as e:
        logger.warning(f"Error formatting sources: {e}")
        return sources


def _escape_markdown(text: str) -> str:
    """
    Escapes Markdown to be rendered verbatim in the frontend in some scenarios
    """
    if not text:
        return ""
    # Escape unordered list items like * item, + item, - item
    text = re.sub(r"^(\s*)([*+-])(\s+)", r"\1\\\2\3", text, flags=re.MULTILINE)
    # Escape ordered list items like 1. item
    text = re.sub(r"^(\s*)(\d+\.)(\s+)", r"\1\\\2\3", text, flags=re.MULTILINE)
    text = text.replace("|", "\\|")
    text = text.replace("\n", "\\n")
    return text


def redact_urls(text: str) -> str:
    """
    Redact URLs from markdown text and replace them with "link redacted".
    
    This function handles:
    - Markdown links: [text](url)
    - HTML links: <a href="url">text</a>
    - Plain URLs: http://example.com or https://example.com
    - URLs with various protocols and formats
    
    Args:
        text: The markdown text containing URLs to redact
        
    Returns:
        The text with all URLs replaced by "link redacted"
    """
    if not text:
        return ""

    # Pattern for markdown links: [text](url)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'[\1](link redacted)', text)

    # Pattern for HTML anchor tags: <a href="url">text</a>
    # Handle both single and double quotes
    text = re.sub(r'<a\s+href\s*=\s*["\']([^"\']*)["\']([^>]*)>([^<]*)</a>',
                  r'<a href="link redacted"\2>\3</a>',
                  text,
                  flags=re.IGNORECASE)

    # Pattern for plain URLs (http/https/ftp/etc.)
    # Match URLs but don't include trailing punctuation that's likely sentence punctuation
    url_pattern = r'\b(?:https?|ftp|ftps|file)://[^\s<>"{}|\\^`\[\]]+(?<![.,!?;:)])'
    text = re.sub(url_pattern, 'link redacted', text, flags=re.IGNORECASE)

    # Handle mailto URLs (both with and without ://)
    mailto_pattern = r'\bmailto:(?://)?[^\s<>"{}|\\^`\[\]]+(?<![.,!?;:)])'
    text = re.sub(mailto_pattern, 'link redacted', text, flags=re.IGNORECASE)

    # Pattern for www. URLs without protocol
    www_pattern = r'\bwww\.[^\s<>"{}|\\^`\[\]]+(?<![.,!?;:)])'
    text = re.sub(www_pattern, 'link redacted', text, flags=re.IGNORECASE)

    return text


def get_max_source_number(sources_text: str) -> int:
    """
    Extract the maximum source number from a string containing sources in the format:
    
    ___
    **Source** 1
    other stuff
    ___
    **Source** 2
    other stuff
    etc
    
    Args:
        sources_text: String containing sources with **Source** X format
        
    Returns:
        The maximum source number found, or 0 if no sources are found
    """
    if not sources_text:
        return 0

    # Pattern to match "**Source** X" where X is a number
    pattern = r'\*\*Source\*\*\s*(\d+)'
    matches = re.findall(pattern, sources_text)

    if not matches:
        return 0

    # Convert matches to integers and return the maximum
    source_numbers = [int(match) for match in matches]
    return max(source_numbers)
