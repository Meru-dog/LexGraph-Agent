"""LLM inference client — Gemini (Phase 2-3) → fine-tuned LLaMA via vLLM (Phase 4)."""

import os
from typing import Optional, AsyncGenerator

LLAMA_ENDPOINT = os.getenv("LLAMA_ENDPOINT", "http://localhost:8080")
USE_VLLM = os.getenv("USE_VLLM", "false").lower() == "true"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")


class LlamaClient:
    """LLM inference client.

    Phase 2-3: Google Gemini API (gemini-1.5-pro) as stand-in for fine-tuned LLaMA.
    Phase 4:   Swap to fine-tuned LLaMA 3.1 8B via vLLM endpoint with QLoRA adapters.
    """

    def __init__(self):
        self._gemini_model = None

    def _get_gemini_model(self, system: str):
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        return genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            generation_config={"temperature": 0.1, "max_output_tokens": 1024},
        )

    async def generate(
        self,
        prompt: str,
        system: str = "You are a legal expert specializing in JP/US law.",
        adapter: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        """Generate a legal response.

        Phase 2-3: Gemini API.
        Phase 4:   vLLM + QLoRA adapter selected by adapter_router.
        """
        if USE_VLLM:
            return await self._vllm_generate(prompt, system, adapter, max_tokens, temperature)

        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        response = model.generate_content(prompt)
        return response.text

    async def stream(
        self,
        prompt: str,
        system: str = "You are a legal expert specializing in JP/US law.",
        adapter: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from Gemini."""
        if USE_VLLM:
            async for token in self._vllm_stream(prompt, system, adapter):
                yield token
            return

        import google.generativeai as genai
        import asyncio

        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            generation_config={"temperature": 0.1, "max_output_tokens": 1024},
        )

        # Gemini streaming is synchronous — run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response_iter = await loop.run_in_executor(
            None, lambda: model.generate_content(prompt, stream=True)
        )
        for chunk in response_iter:
            if chunk.text:
                yield chunk.text

    async def _vllm_generate(
        self, prompt: str, system: str, adapter: Optional[str], max_tokens: int, temperature: float
    ) -> str:
        """Phase 4: call vLLM OpenAI-compatible endpoint with LoRA adapter."""
        import httpx

        payload = {
            "model": adapter or "llama-3.1-8b",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{LLAMA_ENDPOINT}/v1/chat/completions", json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def _vllm_stream(
        self, prompt: str, system: str, adapter: Optional[str]
    ) -> AsyncGenerator[str, None]:
        """Phase 4: streaming from vLLM endpoint."""
        import httpx, json

        payload = {
            "model": adapter or "llama-3.1-8b",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": True,
        }
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", f"{LLAMA_ENDPOINT}/v1/chat/completions", json=payload, timeout=120) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        data = json.loads(line[6:])
                        delta = data["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta

    def classify_risk(self, text: str, context: str, adapter: Optional[str] = None) -> str:
        """Synchronous risk classification — Phase 2 uses heuristics, Phase 4 uses LLaMA."""
        from tools.risk_classifier import risk_classifier
        return risk_classifier(text, context)


llama_client = LlamaClient()
