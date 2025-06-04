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
    try:
        # Split sources into individual entries
        source_entries = re.split(r'(?=---\nSOURCE \d+ QUERY:)', sources)
        formatted_sources = []
     
        
        for idx, entry in enumerate(source_entries):
            source_num = 0
            if not entry.strip():
                continue
                
            # Split into query, answer, and citations using a more precise pattern
            # This pattern looks for newlines followed by QUERY:, ANSWER:, or CITATION(S):
            # but only if they're not preceded by a pipe (|) character (markdown table)
            src_parts = re.split(r'(?<!\|)\n(?=QUERY:|ANSWER:|CITATION(?:S)?:)', entry.strip())
            
            entry_parts = []
            for part in src_parts:
                if re.match(r'^---\nSOURCE \d+ QUERY:*', part):
                    source_num = re.search(r'^---\nSOURCE (\d+)', part).group(1)
                    part = f"**Query:** {re.sub(r'^---\nSOURCE \d+ QUERY:*', '', part).strip()}"
                
                if re.match(r'ANSWER:*', part):
                    part = f"**Answer:** {re.sub(r'^ANSWER:*', '', part).strip()}"

                if re.match(r'^CITATION(?:S)?:*', part):
                    part = f"**Citations:** {re.sub(r'^CITATION(?:S)?:*', '', part).strip()}"

                entry_parts.append(part)


                formatted_entry = f"""
---
**Source** {source_num} \n \n 
{'\n \n'.join(entry_parts)}
"""

            formatted_sources.append(formatted_entry)
        
        return "\n".join(formatted_sources)
    except Exception as e:
        logger.warning(f"Error formatting sources: {e}")
        return sources
