# Purpose: LLMClient protocol, OllamaClient (local HTTP with JSON schema & thinking disabled), FakeClient, and NullClient.
# contract_version: 1.0.0
# Implements: TECH_PLAN §11 (GenAI layer) and R1_E_genai_reports.md #3.

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import requests

from .models import Prompt


class LLMClientError(Exception):
    """Raised when an LLM client is unavailable, times out, or returns an HTTP/transport error."""


@dataclass(frozen=True)
class LLMResponse:
    raw_text: str
    model: str
    latency_ms: float
    tokens_in: int
    tokens_out: int


@runtime_checkable
class LLMClient(Protocol):
    model_name: str

    def generate(self, prompt: Prompt) -> LLMResponse:
        ...


class NullClient:
    """Always unavailable client that forces the deterministic template path."""

    model_name: str = "template_fallback"

    def generate(self, prompt: Prompt) -> LLMResponse:
        raise LLMClientError("NullClient: LLM is intentionally disabled; using deterministic template path.")


class FakeClient:
    """
    Scripted LLM client for unit, fuzz, and failure-mode tests.
    Accepts either:
    - a list of scripted responses (str, Exception, dict, or LLMResponse), consumed in order (or cycling if cycle=True), or
    - a callable `handler(prompt: Prompt, call_index: int) -> str | dict | LLMResponse`.
    Also records every Prompt received in `captured_prompts` for privacy assertions.
    """

    def __init__(
        self,
        responses: list[Any] | Callable[[Prompt, int], Any] | None = None,
        model_name: str = "fake_client",
        cycle: bool = False,
        simulated_latency_ms: float = 2.0,
        tokens_in: int = 420,
        tokens_out: int = 160,
    ) -> None:
        self.model_name = model_name
        self._responses = responses
        self._cycle = cycle
        self._simulated_latency_ms = simulated_latency_ms
        self._default_tokens_in = tokens_in
        self._default_tokens_out = tokens_out
        self.call_count: int = 0
        self.captured_prompts: list[Prompt] = []

    def generate(self, prompt: Prompt) -> LLMResponse:
        idx = self.call_count
        self.call_count += 1
        self.captured_prompts.append(prompt)

        if callable(self._responses):
            item = self._responses(prompt, idx)
        elif isinstance(self._responses, list) and len(self._responses) > 0:
            if idx < len(self._responses):
                item = self._responses[idx]
            elif self._cycle:
                item = self._responses[idx % len(self._responses)]
            else:
                raise LLMClientError("FakeClient: scripted responses exhausted.")
        else:
            raise LLMClientError("FakeClient: no responses configured.")

        if isinstance(item, Exception):
            raise item
        if isinstance(item, LLMResponse):
            return item
        if isinstance(item, dict):
            import json
            raw = json.dumps(item, ensure_ascii=False)
        else:
            raw = str(item)

        return LLMResponse(
            raw_text=raw,
            model=self.model_name,
            latency_ms=self._simulated_latency_ms,
            tokens_in=self._default_tokens_in,
            tokens_out=self._default_tokens_out,
        )


class OllamaClient:
    """
    HTTP client for local Ollama (`http://localhost:11434/api/chat`).
    - Enforces JSON-schema constrained output via `format=prompt.output_schema`.
    - Sets `temperature=0.3`.
    - Explicitly disables thinking mode (`think=False`) for Qwen3 models.
    - Enforces an 8.0s timeout with one transport retry on transient failure.
    """

    def __init__(
        self,
        model_name: str = "qwen3:4b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
        timeout_s: float = 8.0,
        max_retries: int = 1,
        num_gpu: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.num_gpu = num_gpu
        self._session = session or requests.Session()
        self.captured_prompts: list[Prompt] = []

    def generate(self, prompt: Prompt) -> LLMResponse:
        self.captured_prompts.append(prompt)
        url = f"{self.base_url}/api/chat"

        options: dict[str, Any] = {
            "temperature": self.temperature,
            "num_predict": 450,
        }
        if self.num_gpu is not None:
            options["num_gpu"] = self.num_gpu

        user_content = prompt.user
        is_qwen3 = "qwen3" in self.model_name.lower()
        if is_qwen3 and not user_content.lstrip().startswith("/no_think"):
            user_content = "/no_think\n" + user_content

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": user_content},
            ],
            "format": prompt.output_schema,
            "stream": False,
            "options": options,
        }
        if is_qwen3:
            payload["think"] = False

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                resp = self._session.post(url, json=payload, timeout=self.timeout_s)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if resp.status_code != 200:
                    raise LLMClientError(f"Ollama HTTP {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                msg = data.get("message", {})
                raw_text = msg.get("content", "")
                if not isinstance(raw_text, str) or not raw_text.strip():
                    raise LLMClientError("Ollama returned empty message content.")
                tokens_in = int(data.get("prompt_eval_count") or max(1, len(prompt.system + prompt.user) // 4))
                tokens_out = int(data.get("eval_count") or max(1, len(raw_text) // 4))
                return LLMResponse(
                    raw_text=raw_text,
                    model=self.model_name,
                    latency_ms=round(elapsed_ms, 2),
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )
            except Exception as exc:
                last_err = exc
                if attempt >= self.max_retries:
                    break
        raise LLMClientError(f"OllamaClient failed after {self.max_retries + 1} attempts: {last_err}")
