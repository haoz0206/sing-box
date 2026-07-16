# Distribution policy acceptance — 2026-07-16

Scope: versioned root-owned wheel installation, atomic package activation,
stable non-root and privileged launchers, fixed directory permissions, native
authorization parser, non-interactive operator access, read-only live-config
inspection, and no-arguments helper restriction. This is container acceptance,
not a live init-system smoke test.

## Inputs

- Debian 12: `docker.io/library/debian@sha256:63a496b5d3b99214b39f5ed70eb71a61e590a77979c79cbee4faf991f8c0783e`
- Ubuntu 24.04: `docker.io/library/ubuntu@sha256:52df9b1ee71626e0088f7d400d5c6b5f7bb916f8f0c82b474289a4ece6cf3faf`
- Alpine 3.20: `docker.io/library/alpine@sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e`
- Final tested wheel SHA-256: `08a89430dcae73e469397e85836c5290018a5df99113be5b6d39727fdcd1671e`
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
- `sb-manager-install` created a release named by package version plus exact
  wheel SHA-256, activated it through a relative `current` symlink, and exposed
  root-owned real launchers under `/opt/sing-box-manager/bin`.
- The dedicated non-root operator executed the stable `sb-manager --help`
  launcher through the activated release on every distribution.
- Debian 12 and Ubuntu 24.04 accepted the generated fragment with
  `/usr/sbin/visudo -cf`; the fragment mode was `0440`.
- Alpine 3.20 accepted the generated fragment with `/usr/bin/doas -C`; the
  fragment mode was `0600`.
- The stable helper launcher was root-owned, mode `0755`, and authorized at
  `/opt/sing-box-manager/bin/sb-manager-privileged`.
- `/var/lib/sing-box-manager/incoming` was mode `0770` and owned by
  `root:sing-box-manager`.
- The dedicated non-root operator reached the helper via `sudo -n` or `doas -n`
  without a password prompt.
- The operator invoked `inspect-config` through that policy and received only
  existence state plus an optional SHA-256 fingerprint; configuration content
  was never returned.
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
