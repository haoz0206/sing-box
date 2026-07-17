# Adopt existing configuration by exact fingerprint

The manager will never infer ownership by parsing an existing sing-box file or
by recognizing familiar inbounds. Adoption records the exact SHA-256 of the
operator-reviewed live configuration as the next replacement precondition;
apply rechecks that fingerprint immediately before mutation, and every
successful manager apply records the fingerprint of its generated successor.
This avoids importing secrets or unsupported semantics while preventing both
silent takeover and changes between review and apply. Semantic import remains a
separate, explicitly supported workflow.

The complete Textual journey renders loading, fingerprint review, confirmation,
progress, typed rejection, terminal evidence, and unknown-result recovery
through the validated interface copy catalog. Fingerprints, desired-state
revisions, and typed diagnostics remain literal evidence with markup disabled.
An unclassified planning exception claims no change; an unclassified exception
after confirmation treats the replacement-precondition result as unknown and
requires fresh live-configuration-identity inspection before retry. Success
offers one explicit return action that clears the workflow stack and recomposes
the dashboard, so the operator never returns to a stale adoption plan.
