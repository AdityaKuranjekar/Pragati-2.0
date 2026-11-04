"""
Agent D — Public Validation (`ml.public_validation`).

Validates DataMoat's early-warning and knowledge-tracing/mastery methodologies
on two real, independently collected public datasets:
1. OULAD (Open University Learning Analytics Dataset, CC BY 4.0) — early withdrawal
   prediction at observation windows day 14, 28, 42, and 60, plus a real-data
   privacy-cost ablation (Academic Tier A vs. Academic + Behavioural Tier D).
2. ASSISTments 2009-2010 Skill Builder — next-response prediction under the
   standardized pyKT 5-fold student-held-out protocol (Liu et al., NeurIPS 2022).
"""

from .oulad import (
    OULADWindowResult,
    build_oulad_features_as_of,
    aggregate_vle_daily,
    load_or_build_vle_daily_cache,
    evaluate_oulad_window,
    run_oulad_suite,
)
from .assistments import (
    OnlineRaschEAP,
    BKTModel,
    LogisticItemStudentBaseline,
    preprocess_assistments_pykt,
    evaluate_assistments_pykt,
)

__all__ = [
    "OULADWindowResult",
    "build_oulad_features_as_of",
    "aggregate_vle_daily",
    "load_or_build_vle_daily_cache",
    "evaluate_oulad_window",
    "run_oulad_suite",
    "OnlineRaschEAP",
    "BKTModel",
    "LogisticItemStudentBaseline",
    "preprocess_assistments_pykt",
    "evaluate_assistments_pykt",
]
