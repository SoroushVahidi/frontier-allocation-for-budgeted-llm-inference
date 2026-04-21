from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]



def test_canonical_repo_files_exist() -> None:
    required = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "requirements.txt",
        REPO_ROOT / "Makefile",
        REPO_ROOT / "docs" / "README.md",
        REPO_ROOT / "scripts" / "README.md",
        REPO_ROOT / "experiments" / "frontier_router.py",
    ]
    missing = [str(path.relative_to(REPO_ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing canonical repo files: {missing}"



def test_stable_current_docs_exist() -> None:
    required = [
        REPO_ROOT / "docs" / "CANONICAL_INSTALL_AND_DEV.md",
        REPO_ROOT / "docs" / "CURRENT_METHOD.md",
        REPO_ROOT / "docs" / "CURRENT_RESULTS.md",
        REPO_ROOT / "docs" / "CURRENT_REFERENCES.md",
        REPO_ROOT / "docs" / "CURRENT_NEXT_STEPS.md",
        REPO_ROOT / "docs" / "CANONICAL_PAPER_WORKING_SET.md",
    ]
    missing = [str(path.relative_to(REPO_ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing stable current docs: {missing}"
