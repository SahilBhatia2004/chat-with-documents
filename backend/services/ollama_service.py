import httpx
import json
from typing import AsyncGenerator, List, Dict
from config import OLLAMA_BASE_URL, OLLAMA_MODEL


async def generate_chat_title(first_message: str) -> str:
    """Generate a short dynamic title for a chat based on the first message."""
    prompt_messages = [
        {
            "role": "system",
            "content": "Generate a very short title (max 6 words) for a chat that starts with the following message. Return ONLY the title, nothing else."
        },
        {"role": "user", "content": first_message}
    ]
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": prompt_messages, "stream": False}
            )
            if response.status_code == 200:
                data = response.json()
                title = data.get("message", {}).get("content", "").strip()
                return title[:100] if title else "New Chat"
    except Exception:
        pass
    # Fallback: use first 50 chars of message
    return first_message[:50].strip() + ("..." if len(first_message) > 50 else "")


async def generate_response_stream(messages: List[Dict]) -> AsyncGenerator[str, None]:
    """Stream response from Ollama API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": True}
        ) as response:
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue


async def generate_response_sync(messages: List[Dict]) -> str:
    """Non-streaming response from Ollama API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("message", {}).get("content", "")
        else:
            raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
