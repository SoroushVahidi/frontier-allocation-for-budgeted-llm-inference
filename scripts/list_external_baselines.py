#!/usr/bin/env python3
"""Print external baseline registry (clone URLs + docs). No network required."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
path = REPO_ROOT / "configs" / "external_baselines_registry.json"
data = json.loads(path.read_text(encoding="utf-8"))
for key, meta in sorted(data.get("baselines", {}).items()):
    url = meta.get("clone_url") or "(no clone_url)"
    doc = meta.get("doc", "")
    print(f"{key}\t{meta.get('integration', '')}\t{url}\t{doc}")
