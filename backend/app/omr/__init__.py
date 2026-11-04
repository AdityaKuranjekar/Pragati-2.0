"""Offline OMR sheet reader (phase P7). See docs/OMR_README.md."""

from .reader import OmrResult, QuestionRead, Quality, UncertainCell, available_layouts, load_layout, read_sheet, render_overlay
from .score import score

__all__ = [
    "OmrResult", "QuestionRead", "Quality", "UncertainCell",
    "available_layouts", "load_layout", "read_sheet", "render_overlay", "score",
]
