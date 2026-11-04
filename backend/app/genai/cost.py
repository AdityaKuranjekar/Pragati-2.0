# Purpose: CostMeter for tracking LLM token usage, per-report INR cost, and monthly institute caps.
# contract_version: 1.0.0
# Implements: TECH_PLAN §11 (GenAI layer), §16 (Cost model), and R1_E_genai_reports.md #7.

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .models import GENAI_DIR


@lru_cache(maxsize=4)
def _load_pricing_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class CostMeter:
    """
    Tracks LLM token counts and INR costs per report and per institute.
    Enforces a monthly INR cap per institute, triggering deterministic template fallback when reached.
    """

    def __init__(
        self,
        pricing_path: Path | None = None,
        monthly_cap_inr: float | None = None,
    ) -> None:
        self.pricing_path = pricing_path or (GENAI_DIR / "pricing.yaml")
        self.config: dict[str, Any] = _load_pricing_yaml(self.pricing_path)

        self.fx_inr_per_usd: float = float(self.config.get("fx_inr_per_usd", 90.0))
        self.default_cap_inr: float = (
            float(monthly_cap_inr)
            if monthly_cap_inr is not None
            else float(self.config.get("default_monthly_cap_inr_per_institute", 500.0))
        )
        self.models: dict[str, dict[str, Any]] = self.config.get("models", {})
        self._spend_by_institute_month: dict[tuple[str, str], float] = {}
        self._tokens_by_institute_month: dict[tuple[str, str], tuple[int, int]] = {}
        self._reports_by_institute_month: dict[tuple[str, str], int] = {}

    def get_model_pricing(self, model: str) -> dict[str, Any]:
        if model in self.models:
            return self.models[model]
        # Default for unknown local Ollama tag: ₹0 marginal cost
        return {
            "provider": "ollama_local",
            "input_usd_per_1m": 0.0,
            "output_usd_per_1m": 0.0,
            "input_inr_per_1m": 0.0,
            "output_inr_per_1m": 0.0,
            "marginal_cost_inr": 0.0,
            "verified": False,
            "source": "unknown_local_model_zero_marginal",
        }

    def compute_cost_inr(self, model: str, tokens_in: int, tokens_out: int) -> float:
        info = self.get_model_pricing(model)
        in_inr_per_1m = float(info.get("input_inr_per_1m", 0.0))
        out_inr_per_1m = float(info.get("output_inr_per_1m", 0.0))
        cost = (max(0, int(tokens_in)) * in_inr_per_1m + max(0, int(tokens_out)) * out_inr_per_1m) / 1_000_000.0
        return round(cost, 6)

    def can_spend(
        self,
        institute_key: str = "default",
        month_key: str = "current",
        estimated_cost_inr: float = 0.0,
        cap_inr: float | None = None,
    ) -> bool:
        cap = self.default_cap_inr if cap_inr is None else float(cap_inr)
        spent = self._spend_by_institute_month.get((institute_key, month_key), 0.0)
        if spent >= cap:
            return False
        if spent + max(0.0, estimated_cost_inr) > cap:
            return False
        return True

    def record(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        institute_key: str = "default",
        month_key: str = "current",
    ) -> float:
        cost = self.compute_cost_inr(model, tokens_in, tokens_out)
        key = (institute_key, month_key)
        self._spend_by_institute_month[key] = round(self._spend_by_institute_month.get(key, 0.0) + cost, 6)
        prev_in, prev_out = self._tokens_by_institute_month.get(key, (0, 0))
        self._tokens_by_institute_month[key] = (prev_in + int(tokens_in), prev_out + int(tokens_out))
        self._reports_by_institute_month[key] = self._reports_by_institute_month.get(key, 0) + 1
        return cost

    def get_spend_inr(self, institute_key: str = "default", month_key: str = "current") -> float:
        return self._spend_by_institute_month.get((institute_key, month_key), 0.0)

    def get_summary(self, institute_key: str = "default", month_key: str = "current") -> dict[str, Any]:
        key = (institute_key, month_key)
        t_in, t_out = self._tokens_by_institute_month.get(key, (0, 0))
        return {
            "institute_key": institute_key,
            "month_key": month_key,
            "reports_count": self._reports_by_institute_month.get(key, 0),
            "tokens_in": t_in,
            "tokens_out": t_out,
            "total_cost_inr": self._spend_by_institute_month.get(key, 0.0),
            "monthly_cap_inr": self.default_cap_inr,
        }

    def estimate_monthly_student_cost_inr(
        self,
        model: str,
        avg_tokens_in: int = 600,
        avg_tokens_out: int = 300,
        reports_per_month: int | None = None,
    ) -> dict[str, float]:
        rpm = int(reports_per_month or self.config.get("reports_per_student_per_month", 4))
        per_report = self.compute_cost_inr(model, avg_tokens_in, avg_tokens_out)
        return {
            "cost_per_report_inr": per_report,
            "reports_per_student_month": float(rpm),
            "cost_per_student_month_inr": round(per_report * rpm, 6),
        }
