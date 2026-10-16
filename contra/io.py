"""Ingest: read xlsx/csv and find the Like / Dislike columns. Never modifies the input file."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

LIKE_RE = re.compile(r"\b(like[sd]?|love[sd]?|enjoy\w*|good|positive|best|favou?rite)\b", re.I)
DISLIKE_RE = re.compile(r"\b(dislike[sd]?|hate[sd]?|improv\w*|bad|negative|worst|annoy\w*|least)\b", re.I)


class ColumnDetectionError(ValueError):
    pass


def read_table(path: str | Path, sheet: str | int | None = None) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".csv", ".tsv"}:
        return pd.read_csv(path, sep="\t" if path.suffix.lower() == ".tsv" else ",")
    return pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)


def list_sheets(path: str | Path) -> list[str]:
    if Path(path).suffix.lower() in {".csv", ".tsv"}:
        return []
    return pd.ExcelFile(path).sheet_names


def detect_columns(df: pd.DataFrame) -> tuple[str, str]:
    """Find (like_col, dislike_col) by header regex. Raises with candidates if ambiguous."""
    cols = [str(c) for c in df.columns]
    dislikes = [c for c in cols if DISLIKE_RE.search(c)]
    # "dislike" contains "like": exclude dislike columns from like candidates
    likes = [c for c in cols if LIKE_RE.search(c) and c not in dislikes]
    if len(likes) == 1 and len(dislikes) == 1:
        return likes[0], dislikes[0]
    raise ColumnDetectionError(
        f"Could not uniquely detect Like/Dislike columns. Like candidates: {likes}; "
        f"Dislike candidates: {dislikes}. Pass them explicitly (--like-col / --dislike-col)."
    )
