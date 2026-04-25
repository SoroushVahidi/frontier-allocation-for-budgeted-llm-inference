# ANONYMIZATION_AUDIT_20260425T153307Z

## Scope
Repository-wide text scan for identity strings, path leaks, key-like patterns, and external links.

## Output bundle
- `outputs/anonymization_audit_20260425T153307Z/manifest.json`
- `outputs/anonymization_audit_20260425T153307Z/identity_string_scan.csv`
- `outputs/anonymization_audit_20260425T153307Z/path_leak_scan.csv`
- `outputs/anonymization_audit_20260425T153307Z/api_secret_scan.csv`
- `outputs/anonymization_audit_20260425T153307Z/external_link_scan.csv`
- `outputs/anonymization_audit_20260425T153307Z/files_changed.csv`
- `outputs/anonymization_audit_20260425T153307Z/remaining_risks.csv`

## Status labels
- `fixed`
- `safe_context`
- `intentional_public_citation`
- `needs_manual_review`

## Notes
- Canonical reviewer-facing docs were rewritten to anonymous language.
- Legacy historical artifacts remain in repository for scientific provenance and are tracked as `needs_manual_review` when potentially deanonymizing.
- Normal scholarly citations are retained.
