from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_public_release_health_check_passes() -> None:
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/check_repo_health.py"],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stdout + result.stderr

