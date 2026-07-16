# Adopt existing configuration by exact fingerprint

The manager will never infer ownership by parsing an existing sing-box file or
by recognizing familiar inbounds. Adoption records the exact SHA-256 of the
operator-reviewed live configuration as the next replacement precondition;
apply rechecks that fingerprint immediately before mutation, and every
successful manager apply records the fingerprint of its generated successor.
This avoids importing secrets or unsupported semantics while preventing both
silent takeover and changes between review and apply. Semantic import remains a
separate, explicitly supported workflow.
