from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter

from sourceatlas.api.deps import AppSettings

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation")
def latest(settings: AppSettings) -> list[dict[str, Any]]:
    """Latest stored benchmark report per label (written by `make evaluate*`)."""
    root = settings.eval_results_dir
    out = []
    for f in sorted(root.glob("latest-*.json")) if root.is_dir() else []:
        try:
            out.append(json.loads(f.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    return out
