# Privileged helper deployment

Status: pre-release operator contract  
Last updated: 2026-07-16

`sb-manager-privileged` is a single-shot root helper. It accepts one JSON request
on standard input, performs one allowlisted operation, writes one JSON result,
and exits. It has no network client and accepts no command-line arguments or
path overrides.

## Security prerequisites

Do not run the helper from a developer editable environment. Before granting
sudo, doas, or polkit authorization, all of the following must be owned by root
and not writable by the invoking user or group:

- the Python interpreter and private virtual environment;
- the `sb-manager-privileged` console script;
- the installed `sb_manager` package and its parent directories;
- the fixed work, installation, and lock parent directories.

Use an absolute helper path in authorization policy. Never authorize a generic
Python interpreter, shell, user-selected script path, or arbitrary arguments.
The policy installer requires the operator to select sudo or doas and an
already existing dedicated group; it never creates accounts or grants general
administrative access.

## Root-owned installation

Build the wheel in CI or a trusted development environment and deploy it with a
reviewed dependency wheelhouse. `sb-manager-install` creates an immutable,
versioned virtual environment and atomically activates it behind `current`.
Stable real launchers remain under `/opt/sing-box-manager/bin`; only the small
helper launcher is authorized as root.

On Debian or Ubuntu:

```bash
sudo groupadd --system sing-box-manager
sudo usermod --append --groups sing-box-manager OPERATOR_USER
sudo python3 -m venv /root/sb-manager-bootstrap
sudo /root/sb-manager-bootstrap/bin/pip install \
  --no-index --find-links /path/to/reviewed-wheelhouse \
  /path/to/sing_box_manager-0.1.0-py3-none-any.whl
sudo /root/sb-manager-bootstrap/bin/sb-manager-install \
  --wheel /path/to/sing_box_manager-0.1.0-py3-none-any.whl \
  --wheelhouse /path/to/reviewed-wheelhouse
sudo /root/sb-manager-bootstrap/bin/sb-manager-install \
  --wheel /path/to/sing_box_manager-0.1.0-py3-none-any.whl \
  --wheelhouse /path/to/reviewed-wheelhouse --confirm
sudo /opt/sing-box-manager/bin/sb-manager-install-policy \
  --authorization sudo --group sing-box-manager
sudo /opt/sing-box-manager/bin/sb-manager-install-policy \
  --authorization sudo --group sing-box-manager --confirm
```

The first installer command is a read-only preview and prints the exact JSON
plan. Review its helper, authorization, and directory paths before repeating
the command with `--confirm`. Only the confirmed command requires root and
changes the host.

The generated sudoers fragment uses the sudoers empty argument string `""`, so
the fixed helper cannot be invoked with command-line arguments. The installer
runs `/usr/sbin/visudo -cf` on a temporary fragment before atomically replacing
`/etc/sudoers.d/sing-box-manager`.

On Alpine:

```bash
doas addgroup -S sing-box-manager
doas addgroup OPERATOR_USER sing-box-manager
doas python3 -m venv /root/sb-manager-bootstrap
doas /root/sb-manager-bootstrap/bin/pip install \
  --no-index --find-links /path/to/reviewed-wheelhouse \
  /path/to/sing_box_manager-0.1.0-py3-none-any.whl
doas /root/sb-manager-bootstrap/bin/sb-manager-install \
  --wheel /path/to/sing_box_manager-0.1.0-py3-none-any.whl \
  --wheelhouse /path/to/reviewed-wheelhouse
doas /root/sb-manager-bootstrap/bin/sb-manager-install \
  --wheel /path/to/sing_box_manager-0.1.0-py3-none-any.whl \
  --wheelhouse /path/to/reviewed-wheelhouse --confirm
doas /opt/sing-box-manager/bin/sb-manager-install-policy \
  --authorization doas --group sing-box-manager
doas /opt/sing-box-manager/bin/sb-manager-install-policy \
  --authorization doas --group sing-box-manager --confirm
```

As with sudo, omit `--confirm` first to review the read-only JSON plan.

The generated doas fragment ends in bare `args`, which requires the helper to
run without arguments. The installer validates it with `/usr/bin/doas -C`
before atomically replacing `/etc/doas.d/sing-box-manager.conf`. Alpine's doas
package loads `/etc/doas.d/*.conf`; confirm this remains enabled in the host's
`/etc/doas.conf`.

Group membership normally requires a new login. Then verify non-interactive
authorization before opening the TUI:

```bash
/usr/bin/sudo -n /opt/sing-box-manager/bin/sb-manager-privileged </dev/null
/usr/bin/doas -n /opt/sing-box-manager/bin/sb-manager-privileged </dev/null
```

Exactly one of these commands is expected for the selected host. An empty
request should be rejected as invalid JSON, which proves authorization reached
the helper without granting a shell. Never authorize `sb-manager`, Python,
pip, a shell, or an operator-writable wrapper as root.

To use the advanced operator-file TLS strategy, deploy reviewed PEM material
under the fixed trusted directory. The private key must not be readable or
writable by group or other users:

```bash
sudo install -o root -g root -m 0644 fullchain.pem \
  /etc/sing-box-manager/tls/server.crt
sudo install -o root -g root -m 0600 private-key.pem \
  /etc/sing-box-manager/tls/server.key
```

Use `doas` instead of `sudo` on Alpine. The TUI stores only these paths in
desired state and never reads or displays private-key contents. At apply time,
the root helper rejects paths outside the trusted directory, symlinks,
non-regular files, non-root ownership, writable certificate files, and any
group/other access to a private key.

## Fixed host paths

| Purpose | Path |
|---|---|
| Versioned Python package releases | `/opt/sing-box-manager/releases` |
| Active Python package release | `/opt/sing-box-manager/current` |
| Stable manager launchers | `/opt/sing-box-manager/bin` |
| Incoming verified archive | `/var/lib/sing-box-manager/incoming` |
| Root-private copy and staging | `/var/lib/sing-box-manager/work` |
| Versioned core installation | `/opt/sing-box-manager/core` |
| Activation lock | `/run/lock/sing-box-manager-core.lock` |
| Managed configuration | `/etc/sing-box/config.json` |
| Installed validation core | `/opt/sing-box-manager/core/current/sing-box` |
| Configuration apply lock | `/run/lock/sing-box-manager-apply.lock` |

The incoming directory may permit a dedicated manager account to create files,
but its parent and the other paths must remain root-controlled. The helper
derives the archive filename from version and architecture, opens it with
`O_NOFOLLOW`, copies at most 256 MiB into private storage, and rechecks the full
SHA-256 before archive parsing.

## Request protocol

Schema version 1 allows `activate-core`:

```json
{
  "schema_version": 1,
  "operation": "activate-core",
  "version": "1.14.0-alpha.45",
  "architecture": "amd64",
  "sha256": "FULL_64_CHARACTER_LOWERCASE_SHA256"
}
```

Unknown, missing, or duplicate fields fail. `architecture` is `amd64` or
`arm64`. On success the helper returns complete activation evidence without
echoing request bytes or file contents:

```json
{
  "schema_version": 1,
  "status": "activated",
  "activation": {
    "version": "1.14.0-alpha.45",
    "distribution_directory": "/opt/sing-box-manager/core/versions/1.14.0-alpha.45-SHA256",
    "binary_path": "/opt/sing-box-manager/core/current/sing-box",
    "activated_target": "versions/1.14.0-alpha.45-SHA256",
    "previous_target": null
  }
}
```

The unprivileged client requires this exact response shape and verifies that
the returned version matches the requested version.

It also allows a fixed-target configuration transaction:

```json
{
  "schema_version": 1,
  "operation": "apply-config",
  "sha256": "FULL_64_CHARACTER_LOWERCASE_SHA256",
  "expected_config_sha256": null
}
```

`expected_config_sha256` is `null` only when the live target must still be
absent. After explicit adoption or a successful manager apply it is the exact
64-character fingerprint previously recorded in desired state. A missing,
unexpected, or changed target is rejected after candidate validation but before
backup or commit.

The corresponding incoming filename is derived as `config-<sha256>.json`.
The request cannot choose its destination, validator, init system, service, or
lock. Before invoking `sing-box check`, the helper rejects duplicate JSON fields
and validates the full document against the exact manager-generated subset:
supported inbound schemas only, unique managed profile tags and ports, one
fixed direct outbound, matching ACME providers under
`/var/lib/sing-box-manager/acme`, and root-owned operator TLS files under
`/etc/sing-box-manager/tls`. Unknown top-level or nested capabilities fail
before any host transaction. On an active systemd host the helper uses
`/usr/bin/systemctl sing-box.service`; otherwise it accepts fixed
`/sbin/rc-service sing-box`. It reuses the transactional validator, atomic
commit, health check, and rollback behavior.

The read-only adoption workflow uses a separate request:

```json
{
  "schema_version": 1,
  "operation": "inspect-config"
}
```

Its response contains only `exists` and `sha256`; configuration content and
secrets never cross the helper protocol. The TUI re-runs this inspection during
confirmation before recording the replacement precondition.

The unprivileged TUI client is available through:

```bash
sb-manager --apply-mode privileged
```

Configuration apply in this mode writes deterministic mode-`0600` incoming
JSON, sends only its SHA-256 to the helper, restores the typed transaction
response, and removes the incoming file. The TUI core update action is
available independently of configuration apply mode: it requires an exact
version and architecture, presents a side-effect-free plan, downloads and
verifies the official immutable asset in a thread worker, then sends the exact
version, architecture, and digest to `activate-core`. The privilege runner is
always invoked with `-n`, so missing authorization fails instead of opening a
hidden password prompt inside the TUI. Supported-host execution remains pending
until the host smoke commands in `SUPPORT.md` pass on each target distribution.
