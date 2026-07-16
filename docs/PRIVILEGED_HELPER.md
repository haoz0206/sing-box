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
The repository intentionally does not install authorization policy because its
owner, invoking account, and host controls are operator decisions.

## Fixed host paths

| Purpose | Path |
|---|---|
| Incoming verified archive | `/var/lib/sing-box-manager/incoming` |
| Root-private copy and staging | `/var/lib/sing-box-manager/work` |
| Versioned core installation | `/opt/sing-box-manager/core` |
| Activation lock | `/run/lock/sing-box-manager-core.lock` |

The incoming directory may permit a dedicated manager account to create files,
but its parent and the other paths must remain root-controlled. The helper
derives the archive filename from version and architecture, opens it with
`O_NOFOLLOW`, copies at most 256 MiB into private storage, and rechecks the full
SHA-256 before archive parsing.

## Request protocol

Schema version 1 currently allows only `activate-core`:

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
`arm64`. The helper emits the active binary path and previous activation target
without echoing request bytes or file contents.

The current helper covers core activation only. Privileged configuration apply
and runtime refresh remain unavailable until they receive separate request
schemas and transaction tests.
