"""Config loading: every lexicon lives in contra/config/*.yaml and can be overridden at run time."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_DIR = Path(__file__).parent / "config"


def load_config(override_dir: str | Path | None = None, overrides: dict[str, dict] | None = None) -> dict[str, dict[str, Any]]:
    """Return {file_stem: parsed_yaml}. Files in override_dir replace defaults of the same name;
    `overrides` ({file_stem: dict}) is shallow-merged on top (used by the Streamlit editor)."""
    cfg: dict[str, dict[str, Any]] = {}
    for path in sorted(DEFAULT_DIR.glob("*.yaml")):
        cfg[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if override_dir:
        for path in sorted(Path(override_dir).glob("*.yaml")):
            cfg[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for stem, vals in (overrides or {}).items():
        cfg.setdefault(stem, {}).update(vals)
    return cfg
