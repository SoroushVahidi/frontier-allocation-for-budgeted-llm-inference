def test_relationready_files_present():
    import os
    repo_root = os.path.dirname(os.path.dirname(__file__))
    docs = [
        "docs/RELATIONREADY_TRAINING_DESIGN.md",
        "docs/RELATIONREADY_ANNOTATION_GUIDE.md",
        "docs/RELATIONREADY_SCHEMA.md",
        "docs/RELATIONREADY_SPLIT_POLICY.md",
        "docs/RELATIONREADY_SYNTH_CORRUPTION_PLAN.md",
    ]
    for p in docs:
        assert os.path.exists(os.path.join(repo_root, p)), f"Missing {p}"
