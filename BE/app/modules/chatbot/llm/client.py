"""
LLM client:
- chat_completion → OpenAI (httpx thuần)
- embed_text      → BGE M3 qua LM Studio / local embedding server
"""

import httpx
import logging
import asyncio
from typing import Type, TypeVar
from pydantic import BaseModel
from openai import AsyncOpenAI
from app.core.config import get_settings
from contextvars import ContextVar
import os
from dotenv import dotenv_values

settings = get_settings()

model_choice_ctx: ContextVar[str] = ContextVar("model_choice", default="1")

def get_dynamic_model_config(choice: str):
    """Lấy cấu hình model từ .env dựa trên lựa chọn (1, 2, 3...)"""
    if not choice or choice == "primary" or choice == "1":
        choice = "1"
    elif choice == "secondary":
        choice = "2"
        
    suffix = f"_{choice}" if choice != "1" else ""
    
    env_vars = dotenv_values(".env")
    
    api_key = env_vars.get(f"OPENAI_API_KEY{suffix}")
    if api_key is None:
        api_key = os.getenv(f"OPENAI_API_KEY{suffix}")
        
    base_url = env_vars.get(f"OPENAI_BASE_URL{suffix}")
    if base_url is None:
        base_url = os.getenv(f"OPENAI_BASE_URL{suffix}")
        
    model = env_vars.get(f"OPENAI_MODEL{suffix}")
    if model is None:
        model = os.getenv(f"OPENAI_MODEL{suffix}")
    
    if choice == "1":
        finetuned = env_vars.get("OPENAI_FINETUNED_MODEL") or os.getenv("OPENAI_FINETUNED_MODEL")
        if finetuned:
            model = finetuned
            
    # OpenAI client requires a non-empty API key. Local servers accept dummy keys.
    if not api_key and base_url:
        api_key = "dummy-key"
            
    if not api_key and not base_url:
        api_key = settings.OPENAI_API_KEY
        base_url = None
        model = getattr(settings, "OPENAI_FINETUNED_MODEL") or getattr(settings, "OPENAI_MODEL", "gpt-4o")
        
    return api_key, base_url, model or "gpt-4o"

async def chat_completion(
    user_prompt: str,
    system_prompt: str = "",
    temperature: float = 0.0,
    max_tokens: int = 2000,
    retries: int = 3,
) -> str:
    logger = logging.getLogger(__name__)
    
    choice = model_choice_ctx.get()
    api_key, base_url, model = get_dynamic_model_config(choice)
    
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )

    for attempt in range(max(1, retries)):
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            res = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
            
            content = res.choices[0].message.content
            if content is None:
                raise ValueError("LLM returned None content")
            return content
        except Exception as exc:
            if attempt < retries - 1:
                logger.warning(f"LLM request error: {exc}. Retry {attempt+1}/{retries}")
                await asyncio.sleep(5)
                continue
            raise
                
    raise RuntimeError("LLM chat completion failed after retries")


T = TypeVar("T", bound=BaseModel)

async def chat_completion_structured(
    user_prompt: str,
    response_format: Type[T],
    system_prompt: str = "",
    temperature: float = 0.0,
    max_tokens: int = 2000,
    retries: int = 3,
) -> T:
    """
    Standard OpenAI structured output using beta.chat.completions.parse
    """
    logger = logging.getLogger(__name__)
    
    choice = model_choice_ctx.get()
    api_key, base_url, model = get_dynamic_model_config(choice)
    
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    for attempt in range(max(1, retries)):
        try:
            res = await client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                response_format=response_format,
            )
            parsed = res.choices[0].message.parsed
            if parsed is None:
                raise ValueError("Parsed result is None")
            return parsed
        except Exception as exc:
            if attempt < retries - 1:
                logger.warning(f"LLM structured request error: {exc}. Retry {attempt+1}/{retries}")
                await asyncio.sleep(5)
                continue
            raise
                
    raise RuntimeError("LLM structured chat completion failed after retries")


async def embed_text(text: str) -> list[float]:
    """Embedding giữ nguyên BGE M3."""
    payload = {
        "model": settings.LM_STUDIO_EMBED_MODEL,
        "input": [text],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(settings.LM_STUDIO_EMBED_URL, json=payload)
        res.raise_for_status()
        data = res.json()
    return data["data"][0]["embedding"]