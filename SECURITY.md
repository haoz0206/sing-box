# Security Policy

Sing-box Manager manages credentials, network listeners, service state, and narrowly scoped root
operations. Please report security problems privately and avoid testing against systems you do not
own or administer.

## Supported versions

| Version | Support |
|---|---|
| Latest `0.x` release | Security fixes and best-effort compatibility updates |
| `main` | Development only; not a supported production release |
| Older `0.x` releases | Upgrade to the latest release before reporting |

This policy will be tightened when the first stable `1.x` release is published.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/haoz0206/sing-box/security/advisories/new).
Do not open a public issue and do not include live credentials, private keys, production state files,
or unredacted host logs.

Include, when available:

- affected Sing-box Manager and sing-box core versions;
- distribution, architecture, Python version, and init system;
- the security boundary crossed and realistic impact;
- minimal reproduction steps using synthetic credentials;
- suggested mitigation or evidence that a safe rollback exists.

You should receive an acknowledgement within 7 days. The maintainer will coordinate validation,
fixing, release timing, and disclosure. Please allow a reasonable remediation period before public
disclosure.

## Scope

High-priority reports include credential disclosure, unauthorized privileged mutation, command or
configuration injection, artifact trust bypass, unsafe rollback, and isolation boundary failures.
General support questions, unsupported host customization, and upstream sing-box vulnerabilities
belong in their respective public support channels unless this project introduces the vulnerability.
