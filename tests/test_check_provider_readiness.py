import json
from pathlib import Path

from scripts import check_provider_readiness as cpr


def test_secret_values_are_redacted(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "secret-cohere-123")
    message = "failed authorization=secret-cohere-123"
    sanitized = cpr.sanitize_error_message(message)
    assert "secret-cohere-123" not in sanitized
    assert "[REDACTED]" in sanitized


def test_missing_env_vars_reported_without_printing(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)

    summary = cpr.build_summary("outputs/test-provider-readiness", "command-a-03-2025")
    assert summary["cohere"]["key_present"] is False
    assert summary["cohere"]["readiness_status"] == "missing_key"
    assert summary["huggingface"]["hf_token_present"] is False
    assert summary["huggingface"]["huggingface_hub_token_present"] is False
    assert summary["huggingface"]["readiness_status"] == "missing_token"
    text_blob = json.dumps(summary)
    assert "COHERE_API_KEY=" not in text_blob
    assert "HF_TOKEN=" not in text_blob
    assert "HUGGINGFACE_HUB_TOKEN=" not in text_blob


def test_output_json_has_required_top_level_fields(tmp_path):
    summary = cpr.build_summary(str(tmp_path), "command-a-03-2025")
    cpr.write_outputs(summary, str(tmp_path))
    payload = json.loads((Path(tmp_path) / "provider_readiness_summary.json").read_text(encoding="utf-8"))
    for key in (
        "timestamp_utc",
        "git_commit_sha",
        "python_executable",
        "python_version",
        "cohere",
        "huggingface",
        "no_secret_values_written",
    ):
        assert key in payload


def test_no_secret_values_written_flag_is_true():
    summary = cpr.build_summary("outputs/test-provider-readiness", "command-a-03-2025")
    assert summary["no_secret_values_written"] is True
