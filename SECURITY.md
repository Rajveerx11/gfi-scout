# Security Policy

## Supported versions

GFI Scout is pre-1.0. Only the **latest release on `main`** receives security
fixes. We do not back-port to older tags.

| Version | Supported |
|---|---|
| `main` (latest) | ✅ |
| Older tags | ❌ |

## Reporting a vulnerability

**Do not open a public GitHub issue for security problems.** Public issues
can be picked up by automated scrapers before a fix lands.

Instead, please report privately via either:

1. **GitHub Security Advisories** — preferred. Open a draft advisory at
   [`/security/advisories/new`](https://github.com/Rajveerx11/gfi-scout/security/advisories/new).
   This keeps the report private until we publish the fix.
2. **Email** — `rajveer11vadnal@gmail.com` with the subject prefix
   `[gfi-scout security]`.

Please include:

- A clear description of the issue and its impact
- Steps to reproduce (minimum reproducible example if possible)
- The affected version / commit
- Your suggested mitigation, if you have one

## What to expect

| Stage | Target turnaround |
|---|---|
| Acknowledgement of report | within 72 hours |
| Initial assessment | within 7 days |
| Fix / mitigation in `main` | depends on severity (see below) |
| Public disclosure | coordinated with reporter, typically after fix release |

| Severity | Definition | Fix target |
|---|---|---|
| **Critical** | RCE, credential exfiltration, account takeover | 7 days |
| **High** | Auth bypass, sensitive-data disclosure | 30 days |
| **Medium** | DoS, partial data exposure | 60 days |
| **Low** | Hardening / defense-in-depth | next regular release |

## Scope

In scope:

- Code in this repository
- Default configuration shipped under [`src/gfi_scout/data/`](src/gfi_scout/data/)
- Documented setup paths in [`docs/SETUP.md`](docs/SETUP.md)

Out of scope:

- Bugs in third-party dependencies (please report upstream; we'll bump after fix)
- Vulnerabilities in MCP clients (Claude Desktop, Cursor, etc.) themselves
- Rate-limit abuse by the *user's own* GitHub token

## Token handling

GFI Scout reads `GITHUB_TOKEN` from the environment / `.env` and never
writes it to logs or disk. Tokens require only `public_repo` scope.

If you suspect your token leaked through this project, **rotate it
immediately** at
[`github.com/settings/tokens`](https://github.com/settings/tokens).

## Hall of fame

Researchers who report valid issues will be credited here (with permission)
after the fix ships.

_No entries yet._
