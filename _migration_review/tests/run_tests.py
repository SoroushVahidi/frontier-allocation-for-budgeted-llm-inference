#!/usr/bin/env python3
"""
Simple test runner for check_provider_readiness tests.
No external dependencies required.
"""

import sys
import os
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_provider_readiness import sanitize_error, check_env_vars, try_import


def test_sanitize_error_redacts_tokens():
    """Test that common token patterns are redacted."""
    print("TEST: test_sanitize_error_redacts_tokens...", end=" ")
    
    # Test HF token pattern
    error_with_hf_token = "Error: Invalid token hf_abc123def456"
    sanitized = sanitize_error(error_with_hf_token)
    assert "[REDACTED]" in sanitized, f"Expected [REDACTED] in {sanitized}"
    assert "hf_abc123def456" not in sanitized, f"Token should be redacted in {sanitized}"
    
    # Test Cohere pattern
    error_with_cohere_token = "Error: Invalid API key co_abc123def456"
    sanitized = sanitize_error(error_with_cohere_token)
    assert "[REDACTED]" in sanitized, f"Expected [REDACTED] in {sanitized}"
    assert "co_abc123def456" not in sanitized, f"Token should be redacted in {sanitized}"
    
    print("✓ PASS")


def test_sanitize_error_redacts_env_var_values():
    """Test that env var values in errors are redacted."""
    print("TEST: test_sanitize_error_redacts_env_var_values...", end=" ")
    
    fake_key = "my_super_secret_key_12345"
    error_msg = f"Authentication failed: {fake_key}"
    
    old_val = os.environ.get("COHERE_API_KEY")
    try:
        os.environ["COHERE_API_KEY"] = fake_key
        sanitized = sanitize_error(error_msg)
        assert fake_key not in sanitized, f"Env var value should be redacted in {sanitized}"
        assert "[REDACTED]" in sanitized, f"Expected [REDACTED] in {sanitized}"
    finally:
        if old_val:
            os.environ["COHERE_API_KEY"] = old_val
        elif "COHERE_API_KEY" in os.environ:
            del os.environ["COHERE_API_KEY"]
    
    print("✓ PASS")


def test_check_env_vars_reports_presence():
    """Test that env var checks return booleans and don't expose values."""
    print("TEST: test_check_env_vars_reports_presence...", end=" ")
    
    old_val = os.environ.get("HF_TOKEN")
    try:
        os.environ["HF_TOKEN"] = "secret_token_value"
        result = check_env_vars(["HF_TOKEN", "COHERE_API_KEY"])
        
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result["HF_TOKEN"] is True, f"Expected True for HF_TOKEN"
        assert result["COHERE_API_KEY"] is False, f"Expected False for COHERE_API_KEY"
        
        # Ensure the secret value is not in the result
        assert "secret_token_value" not in str(result), f"Secret should not be in {result}"
    finally:
        if old_val:
            os.environ["HF_TOKEN"] = old_val
        elif "HF_TOKEN" in os.environ:
            del os.environ["HF_TOKEN"]
    
    print("✓ PASS")


def test_check_env_vars_missing_not_exposed():
    """Test that missing env vars don't leak any information."""
    print("TEST: test_check_env_vars_missing_not_exposed...", end=" ")
    
    old_cohere = os.environ.pop("COHERE_API_KEY", None)
    old_hf = os.environ.pop("HF_TOKEN", None)
    
    try:
        result = check_env_vars(["COHERE_API_KEY", "HF_TOKEN"])
        
        # Should return false for both
        assert result["COHERE_API_KEY"] is False, f"Expected False for missing COHERE_API_KEY"
        assert result["HF_TOKEN"] is False, f"Expected False for missing HF_TOKEN"
        
        # No secret exposure - should be small
        assert len(str(result)) < 100, f"Result too large: {result}"
    finally:
        if old_cohere:
            os.environ["COHERE_API_KEY"] = old_cohere
        if old_hf:
            os.environ["HF_TOKEN"] = old_hf
    
    print("✓ PASS")


def test_try_import_handles_missing():
    """Test try_import gracefully handles missing modules."""
    print("TEST: test_try_import_handles_missing...", end=" ")
    
    success, err = try_import("totally_nonexistent_module_xyz_12345")
    assert success is False, f"Expected False for missing module"
    assert err is not None, f"Expected error message for missing module"
    
    print("✓ PASS")


def test_output_files_exist():
    """Test that output files were created successfully."""
    print("TEST: test_output_files_exist...", end=" ")
    
    import json
    output_dir = Path("/home/soroush/outputs/provider_readiness_20260502T184233Z")
    
    json_path = output_dir / "provider_readiness_summary.json"
    md_path = output_dir / "provider_readiness_report.md"
    
    assert json_path.exists(), f"JSON file not found at {json_path}"
    assert md_path.exists(), f"Markdown file not found at {md_path}"
    
    # Verify JSON is valid
    with open(json_path) as f:
        data = json.load(f)
    
    assert "no_secret_values_written" in data, "Missing no_secret_values_written field"
    assert data["no_secret_values_written"] is True, "no_secret_values_written should be true"
    
    print("✓ PASS")


def test_no_secrets_in_json():
    """Test that no secrets appear in the JSON output."""
    print("TEST: test_no_secrets_in_json...", end=" ")
    
    import json
    output_dir = Path("/home/soroush/outputs/provider_readiness_20260502T184233Z")
    json_path = output_dir / "provider_readiness_summary.json"
    
    with open(json_path) as f:
        data = json.load(f)
        content = json.dumps(data)
    
    # Check that no actual API keys/tokens are exposed
    # (field names like hf_token_present are fine, but actual token values are not)
    # Look for patterns like hf_<random_chars>, co_<random_chars>, sk-<random_chars>
    import re
    
    # Match actual token patterns (not field names)
    secret_patterns = [
        r'hf_[A-Za-z0-9]{20,}',  # HF tokens are long
        r'co_[A-Za-z0-9]{20,}',  # Cohere tokens
        r'sk-[A-Za-z0-9]{20,}',  # OpenAI-style
    ]
    
    for pattern in secret_patterns:
        matches = re.findall(pattern, content)
        assert len(matches) == 0, f"Found potential secret matching {pattern}: {matches}"
    
    print("✓ PASS")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("RUNNING TESTS")
    print("="*60 + "\n")
    
    tests = [
        test_sanitize_error_redacts_tokens,
        test_sanitize_error_redacts_env_var_values,
        test_check_env_vars_reports_presence,
        test_check_env_vars_missing_not_exposed,
        test_try_import_handles_missing,
        test_output_files_exist,
        test_no_secrets_in_json,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
