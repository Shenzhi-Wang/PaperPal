"""
LLM Client Module
Responsible for interacting with LLM API using requests (Gemini-style)
"""

import json
import sys
import time
from typing import Dict, List, Optional

import requests

import config


class LLMClient:
    """LLM Client using requests to call Gemini-style API"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize LLM client

        Args:
            api_key: API key
            base_url: API base URL
            model: Model name
        """
        self.api_key = api_key or config.OPENAI_API_KEY
        self.base_url = base_url or config.OPENAI_BASE_URL
        self.model = model or config.OPENAI_MODEL
        self.max_retries = 3

        if not self.api_key:
            raise ValueError(
                "API_KEY is not set. Please set OPENAI_API_KEY in your .env file "
                "or as an environment variable."
            )

        # Ensure base_url doesn't end with /v1
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]

    def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        Send chat request using requests (Gemini API format)

        Args:
            messages: List of messages in OpenAI format [{"role": "...", "content": "..."}]
            temperature: Temperature parameter
            max_tokens: Maximum tokens
            response_format: Response format (e.g. {"type": "json_object"})

        Returns:
            Model response text
        """
        # Convert OpenAI messages to Gemini contents
        contents = []

        # Collect system instruction if present
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
                break

        # Build contents
        # If we have a system instruction, we prepend it to the first user message
        first_user_idx = -1
        for i, msg in enumerate(messages):
            if msg["role"] == "user":
                first_user_idx = i
                break

        for i, msg in enumerate(messages):
            if msg["role"] == "system":
                continue

            role = "user" if msg["role"] == "user" else "model"
            text = msg["content"]

            if i == first_user_idx and system_instruction:
                text = f"{system_instruction}\n\n{text}"

            contents.append({"role": role, "parts": [{"text": text}]})

        # If no user message was found but we have system instruction
        if not contents and system_instruction:
            contents.append({"role": "user", "parts": [{"text": system_instruction}]})

        url = (
            f"{self.base_url}/v1/models/{self.model}:generateContent?key={self.api_key}"
        )
        headers = {"Content-Type": "application/json"}

        payload = {"contents": contents}
        generation_config = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }

        if response_format and response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"

        payload["generationConfig"] = generation_config

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    url, headers=headers, json=payload, timeout=120
                )
                response.raise_for_status()
                result = response.json()

                if "candidates" not in result or not result["candidates"]:
                    if "error" in result:
                        error_msg = result["error"].get("message", "Unknown API error")
                        raise RuntimeError(f"API Error: {error_msg}")
                    return ""

                parts = result["candidates"][0].get("content", {}).get("parts", [])
                text_chunks = [p.get("text", "") for p in parts if "text" in p]
                return "".join(text_chunks).strip()

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                if status_code == 401:
                    raise PermissionError(
                        f"Authentication failed (401). Please check your API key."
                    )
                elif status_code == 429:
                    if attempt < self.max_retries:
                        time.sleep(2**attempt)
                        continue
                    raise RuntimeError(
                        "LLM API rate limit exceeded. Please try again later."
                    )
                elif status_code == 404:
                    raise ConnectionError(
                        f"Model not found or invalid URL (404): {url}"
                    )
                else:
                    raise RuntimeError(f"HTTP error {status_code}: {e.response.text}")
            except requests.exceptions.ConnectionError:
                raise ConnectionError(
                    f"Failed to connect to LLM API at {self.base_url}. Please check your network."
                )
            except requests.exceptions.Timeout:
                raise ConnectionError("LLM API request timed out.")
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
                raise RuntimeError(f"An unexpected error occurred: {str(e)}")

        return ""

    def chat_json(
        self,
        messages: List[Dict],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> Dict:
        """
        Send chat request and return JSON format
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        if not response:
            return {}

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            return {}


# Global client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get global LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def init_llm_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMClient:
    """Initialize global LLM client"""
    global _llm_client
    _llm_client = LLMClient(api_key=api_key, base_url=base_url, model=model)
    return _llm_client
