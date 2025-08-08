import asyncio
import logging
from typing import Optional, Dict, Any, Tuple, Callable
from langchain_openai import ChatOpenAI
from langchain_core.runnables import Runnable
from langgraph.types import StreamWriter

logger = logging.getLogger(__name__)


def is_think_tag_llm(llm: ChatOpenAI) -> bool:
    """
    Determine if the LLM uses <think> tags for reasoning tokens.
    Returns True for models that use <think> tags (nemotron, deepseek).
    Returns False for models that use reasoning_content (gpt-oss).
    """
    model_name = getattr(llm, 'model_name', '') or getattr(llm, 'model', '')
    logger.info(f"Model name: {model_name}")
    if not model_name:
        return False

    # Models that use <think> tags
    if any(keyword in model_name.lower() for keyword in ['nemotron', 'deepseek']):
        return True

    # Models that use reasoning_content
    if 'gpt-oss' in model_name.lower():
        return False

    # Default to True for backward compatibility
    return True


def update_system_prompt_for_reasoning(system_prompt: str, llm: ChatOpenAI) -> str:
    """
    Update the system prompt for the LLM to enable reasoning if the model supports it.
    Only nemotron models need the system prompt adjustment.
    Maintains backward compatibility with existing code.
    """
    # If no system prompt is provided, use a default
    if not system_prompt or system_prompt.strip() == "":
        system_prompt = "you are a helpful assistant"

    # Only nemotron models need the special reasoning prompt
    if (hasattr(llm, "model_name") and "nemotron" in llm.model_name):
        system_prompt = "detailed thinking on"
    elif (hasattr(llm, "model") and "nemotron" in llm.model):
        system_prompt = "detailed thinking on"

    return system_prompt


def _handle_llm_error(error: Exception, writer: StreamWriter, writer_key: str) -> None:
    """Handle LLM errors and write appropriate error messages."""
    error_msg = str(error)
    logger.error(f"Error with LLM: {error_msg}")

    if "404" in error_msg or "Not Found" in error_msg:
        writer({writer_key: " \n \n ---------------- \n \n LLM endpoint not found (404). Please check that the LLM service is running and the base_url is correct in the configuration."})
    elif "Connection" in error_msg or "timeout" in error_msg.lower():
        writer({writer_key: " \n \n ---------------- \n \n Cannot connect to LLM service. Please check that the LLM service is running and accessible."})
    else:
        writer({writer_key: f" \n \n ---------------- \n \n Error from LLM: {error_msg}"})


async def _execute_with_timeout(
    operation: Callable,
    timeout: Optional[float] = None
) -> Any:
    """Execute an operation with optional timeout."""
    if timeout:
        async with asyncio.timeout(timeout):
            return await operation()
    else:
        return await operation()


def _stream_chain_with_params(
    chain: Runnable,
    input_data: Dict[str, Any],
    stream_usage: bool = True
):
    """Stream from chain with optional stream_usage parameter."""
    if stream_usage:
        return chain.astream(input_data, stream_usage=True)
    else:
        return chain.astream(input_data)


async def _invoke_chain_with_params(
    chain: Runnable,
    input_data: Dict[str, Any],
    stream_usage: bool = True
):
    """Invoke chain with optional stream_usage parameter."""
    if stream_usage:
        return await chain.ainvoke(input_data, stream_usage=True)
    else:
        return await chain.ainvoke(input_data)


async def stream_llm_response_with_reasoning(
    chain: Runnable,
    llm: ChatOpenAI,
    input_data: Dict[str, Any],
    writer: StreamWriter,
    writer_key: str,
    timeout: Optional[float] = None,
    stream_usage: bool = True
) -> Tuple[str, bool]:
    """
    Stream LLM response with reasoning support for both token formats.
    
    Args:
        chain: The LLM chain to execute
        llm: The LLM object
        input_data: Input data for the chain
        writer: StreamWriter for streaming output
        writer_key: Key for the writer
        timeout: Optional timeout in seconds
        stream_usage: Whether to stream usage information
    
    Returns:
        Tuple of (final_response, success_flag)
    """
    if is_think_tag_llm(llm):
        return await _stream_with_think_tags(
            chain, input_data, writer, writer_key, timeout, stream_usage
        )
    else:
        return await _stream_with_reasoning_content(
            chain, input_data, writer, writer_key, timeout, stream_usage
        )


async def _stream_with_think_tags(
    chain: Runnable,
    input_data: Dict[str, Any],
    writer: StreamWriter,
    writer_key: str,
    timeout: Optional[float] = None,
    stream_usage: bool = True
) -> Tuple[str, bool]:
    """Stream LLM response for models that use <think> tags."""
    result = ""
    stop = False

    try:
        async def stream_operation():
            nonlocal result, stop
            async for chunk in _stream_chain_with_params(chain, input_data, stream_usage):
                result += chunk.content
                if "</think>" in chunk.content:
                    stop = True
                if not stop:
                    writer({writer_key: chunk.content})

        await _execute_with_timeout(stream_operation, timeout)
        return result, True

    except asyncio.TimeoutError:
        writer({writer_key: " \n \n ---------------- \n \n Timeout error from reasoning LLM, please try again"})
        return result, False
    except Exception as e:
        _handle_llm_error(e, writer, writer_key)
        return result, False


async def _stream_with_reasoning_content(chain: Runnable,
                                         input_data: Dict[str, Any],
                                         writer: StreamWriter,
                                         writer_key: str,
                                         timeout: Optional[float] = None,
                                         stream_usage: bool = True) -> Tuple[str, bool]:
    """Stream LLM response for models that use reasoning_content."""
    result = ""

    try:

        async def stream_operation():
            nonlocal result
            async for chunk in _stream_chain_with_params(chain, input_data, stream_usage):
                breakpoint()
                # Check for reasoning content in additional_kwargs
                if chunk.additional_kwargs and "reasoning_content" in chunk.additional_kwargs:
                    writer({writer_key: chunk.content})
                    writer({writer_key: chunk.additional_kwargs["reasoning_content"]})

                if hasattr(chunk,
                           'content') and not (chunk.additional_kwargs
                                               and "reasoning_content" in chunk.additional_kwargs):
                    result += chunk.content

        await _execute_with_timeout(stream_operation, timeout)
        return result, True

    except asyncio.TimeoutError:
        writer(
            {writer_key: " \n \n ---------------- \n \n Timeout error from LLM, please try again"})
        return result, False
    except Exception as e:
        _handle_llm_error(e, writer, writer_key)
        return result, False


def remove_think_tags(text: str) -> str:
    """Remove any text in a string that is wrapped in <think> tags."""
    if "<think>" not in text or "</think>" not in text:
        return text

    while "<think>" in text and "</think>" in text:
        start = text.find("<think>")
        end = text.find("</think>") + len("</think>")
        text = text[:start] + text[end:]

    # Handle case where opening <think> tag might be missing
    while "</think>" in text:
        end = text.find("</think>") + len("</think>")
        text = text[end:]

    return text


def remove_reasoning_content(text: str) -> str:
    """
    Remove reasoning content from gpt-oss model responses.
    This is a placeholder function that may need updates based on actual gpt-oss behavior.
    """
    # For now, return the text as-is since we need to understand
    # how gpt-oss models structure their reasoning content in the final result
    return text


def remove_reasoning_tokens(text: str, llm: ChatOpenAI) -> str:
    """Remove reasoning tokens from LLM response based on model type."""
    if is_think_tag_llm(llm):
        return remove_think_tags(text)
    else:
        return remove_reasoning_content(text)


async def invoke_llm_with_reasoning(
    chain: Runnable,
    llm: ChatOpenAI,
    input_data: Dict[str, Any],
    timeout: Optional[float] = None,
    stream_usage: bool = True
) -> str:
    """
    Invoke LLM without streaming, but handle reasoning content appropriately.
    
    Args:
        chain: The LLM chain to execute
        llm: The LLM object
        input_data: Input data for the chain
        timeout: Optional timeout in seconds
        stream_usage: Whether to stream usage information
    
    Returns:
        Final response string
    """
    if is_think_tag_llm(llm):
        return await _invoke_with_think_tags(chain, input_data, timeout, stream_usage)
    else:
        return await _invoke_with_reasoning_content(chain, input_data, timeout, stream_usage)


async def _invoke_with_think_tags(
    chain: Runnable,
    input_data: Dict[str, Any],
    timeout: Optional[float] = None,
    stream_usage: bool = True
) -> str:
    """Invoke LLM for models that use <think> tags."""
    try:
        response = await _execute_with_timeout(
            lambda: _invoke_chain_with_params(chain, input_data, stream_usage),
            timeout
        )
        return response.content if hasattr(response, 'content') else str(response)

    except asyncio.TimeoutError as e:
        logger.error(f"Timeout error from LLM: {e}")
        raise
    except Exception as e:
        logger.error(f"Error invoking LLM: {e}")
        raise


async def _invoke_with_reasoning_content(
    chain: Runnable,
    input_data: Dict[str, Any],
    timeout: Optional[float] = None,
    stream_usage: bool = True
) -> str:
    """Invoke LLM for models that use reasoning_content."""
    try:
        response = await _execute_with_timeout(
            lambda: _invoke_chain_with_params(chain, input_data, stream_usage),
            timeout
        )
        result = response.content if hasattr(response, 'content') else str(response)
        return result

    except asyncio.TimeoutError as e:
        logger.error(f"Timeout error from LLM: {e}")
        raise
    except Exception as e:
        logger.error(f"Error invoking LLM: {e}")
        raise
