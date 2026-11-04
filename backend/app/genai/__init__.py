"""
Pure Python deterministic + local-LLM verified bilingual parent report generator.

Principle:
- Code decides facts (`build_numbers`).
- Prompt carries only facts and `{STUDENT}` / `{INSTITUTE}` placeholders (`render_prompt`).
- The LLM only phrases facts (`LLMClient`, `OllamaClient`, `FakeClient`, `NullClient`).
- A deterministic verifier (`verify`) decides whether the phrasing may ship.
- Human-written bilingual templates (`backend/templates/en/*.j2`, `hi/*.j2`) are the guaranteed fallback path.
"""

from .clients import FakeClient, LLMClient, LLMResponse, NullClient, OllamaClient
from .cost import CostMeter
from .models import NumbersJson, Prompt, Report, TopicItem, VerifyResult
from .pipeline import (
    HOME_TIPS_CATALOG,
    build_numbers,
    export_report_pdf_bytes,
    generate_report,
    render_prompt,
    render_template_output,
    substitute_placeholders,
)
from .verifier import verify

__all__ = [
    "CostMeter",
    "FakeClient",
    "HOME_TIPS_CATALOG",
    "LLMClient",
    "LLMResponse",
    "NullClient",
    "NumbersJson",
    "OllamaClient",
    "Prompt",
    "Report",
    "TopicItem",
    "VerifyResult",
    "build_numbers",
    "export_report_pdf_bytes",
    "generate_report",
    "render_prompt",
    "render_template_output",
    "substitute_placeholders",
    "verify",
]
