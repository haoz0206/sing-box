## Summary

Describe the problem and the resulting behavior. Keep unrelated changes in separate pull requests.

## Validation

List the checks run and any host, distribution, or sing-box version used for integration evidence.

## Checklist

- [ ] Tests cover changed behavior or the pull request explains why no test is needed.
- [ ] `pytest`, Ruff, and mypy pass locally or equivalent CI evidence is available.
- [ ] User-facing behavior and compatibility changes are documented.
- [ ] `CHANGELOG.md` is updated for a user-visible change.
- [ ] Logs, fixtures, screenshots, and examples contain no credentials or private host data.
- [ ] Privileged, network, and release-boundary changes include explicit failure and rollback analysis.
