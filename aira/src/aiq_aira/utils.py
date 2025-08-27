import asyncio
import re
import logging
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

async def async_gen(num_loops: int):
    """
    Utility for retry loops or chunked iterations.
    """
    for i in range(num_loops):
        yield i
        await asyncio.sleep(0.0)


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

def format_sources(sources: str) -> str:
    """
    Format the sources into nicer looking markdown.
    """
    try:
        # Split sources into individual entries
        source_entries = re.split(r'(?=---\nQUERY:)', sources)
        formatted_sources = []
        src_count = 1

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
    Changes '* item' to '\* item', '1. item' to '\1. item', etc.
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
