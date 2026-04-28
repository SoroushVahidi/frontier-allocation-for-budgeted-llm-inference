from pathlib import Path

from scripts import check_repo_health


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_health_check_includes_front_door_claim_docs() -> None:
    required = {
        REPO_ROOT / "docs" / "CANONICAL_START_HERE.md",
        REPO_ROOT / "docs" / "MANUSCRIPT_SUPPORT_DASHBOARD.md",
        REPO_ROOT / "docs" / "PAPER_SOURCE_OF_TRUTH.md",
        REPO_ROOT / "docs" / "PAPER_CLAIMS_AND_EVIDENCE_MAP.md",
        REPO_ROOT / "docs" / "REPO_MAP.md",
    }
    assert required.issubset(set(check_repo_health.REQUIRED_PATHS))


def test_health_check_required_paths_exist() -> None:
    missing = [p for p in check_repo_health.REQUIRED_PATHS if not p.exists()]
    assert not missing, f"Missing check_repo_health required paths: {[str(p.relative_to(REPO_ROOT)) for p in missing]}"
