# Distribution policy acceptance — 2026-07-16

Scope: root-owned wheel installation, fixed directory permissions, native
authorization parser, non-interactive operator access, and no-arguments helper
restriction. This is container acceptance, not a live init-system smoke test.

## Inputs

- Debian 12: `docker.io/library/debian@sha256:63a496b5d3b99214b39f5ed70eb71a61e590a77979c79cbee4faf991f8c0783e`
- Ubuntu 24.04: `docker.io/library/ubuntu@sha256:52df9b1ee71626e0088f7d400d5c6b5f7bb916f8f0c82b474289a4ece6cf3faf`
- Alpine 3.20: `docker.io/library/alpine@sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e`
- Final tested wheel SHA-256: `43a4ce5c86334cf8ce30f6b9f7b677aca67117ea18d5f12813be050bcd62f22e`
- Dependency mode: explicitly authorized package index (`--allow-index`).
- Container engine: Podman 6.0.1.

## Command

```bash
.venv/bin/python -m sb_manager.release.distro_policy_acceptance \
  --wheel dist/sing_box_manager-0.1.0-py3-none-any.whl \
  --allow-index \
  --network host
```

Host networking was needed only because this execution environment exposed its
package proxy on host loopback.

## Result

All three cases emitted `DISTRO_POLICY_ACCEPTANCE_OK`.

- Each installer invocation used the explicit `--confirm` boundary after the
  same command's read-only plan behavior was covered by the command tests.
- Debian 12 and Ubuntu 24.04 accepted the generated fragment with
  `/usr/sbin/visudo -cf`; the fragment mode was `0440`.
- Alpine 3.20 accepted the generated fragment with `/usr/bin/doas -C`; the
  fragment mode was `0600`.
- The helper console script was root-owned and mode `0755`.
- `/var/lib/sing-box-manager/incoming` was mode `0770` and owned by
  `root:sing-box-manager`.
- The dedicated non-root operator reached the helper via `sudo -n` or `doas -n`
  without a password prompt.
- An extra command-line argument was denied by sudo/doas rather than reaching
  the helper.

## Remaining release evidence

- Debian 12 live systemd refresh and health smoke on a recoverable sing-box
  host.
- Ubuntu 24.04 live systemd refresh and health smoke on a recoverable sing-box
  host.
- Alpine 3.20 live OpenRC refresh and health smoke on a recoverable sing-box
  host.
- Stable sing-box 1.14 validation after upstream publishes a stable release.
