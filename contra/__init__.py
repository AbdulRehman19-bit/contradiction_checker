"""Rule-based Like vs Dislike contradiction detector."""
from .engine import PairResult, analyze_dataframe, analyze_pair

__all__ = ["analyze_pair", "analyze_dataframe", "PairResult"]
