# Security Policy

## Scope

This repository contains **additive extensions** built on top of
[Hermes Agent](https://github.com/NousResearch/hermes-agent) (an open-source
project by Nous Research, MIT License). It does **not** contain the upstream
Hermes Agent core, gateway, tools, UI, or any upstream credentials.

## What is NOT in this repository

By design and by audit, this repository **never includes**:

- `.env` files, API keys, tokens, passwords, or any credentials
- VPN configuration or backup artifacts (`*.conf`, `*-vpn-backup*.tar.gz`)
- Private IPs, VPS addresses, or infrastructure topology
- Personal memory files (`MEMORY.md`, `USER.md`), session databases, or
  `experiences.json` runtime data
- Personal project names or operator identifiers
- Absolute filesystem paths tied to a specific deployment

All three scan passes (personal identifiers, secrets, absolute paths) are
documented in the publication audit below and currently return clean.

## Reporting a vulnerability

If you find a security issue in these extensions, please **do not open a
public issue**. Instead, contact the maintainer directly:

- Email: *(set before publishing — replace this line with a monitored address)*

Include a description of the issue, steps to reproduce, and any relevant
files. You will get a response within a reasonable time frame.

For vulnerabilities in **upstream Hermes Agent** itself, report them to the
Nous Research project: <https://github.com/NousResearch/hermes-agent/security>

## Design principles

These extensions follow the same principles as the upstream project:

1. **Additive only.** No upstream file is modified. Every module is a new
   file under a new directory, importable in isolation (subject to upstream
   dependencies documented in `ARCHITECTURE.md`).
2. **Fail-safe.** Intelligence and governance calls are wrapped in
   `try/except` and never block execution.
3. **Evidence over claims.** Every status label in `PROJECT_STATUS.md` is
   backed by a file on disk or a runtime observation. Nothing is asserted
   without a verifiable trace.
4. **Cache-safe.** No extension mutates the conversation prompt prefix or
   rebuilds the system prompt mid-conversation.

## Publication audit

Before any public release, the following checks are run and must return clean:

```bash
# 1. Personal identifiers
grep -rln "<copyright-holder>\|<personal-domain>" .

# 2. Secrets
grep -rln "sk-[a-zA-Z0-9]\{20\}\|Bearer [a-zA-Z0-9]\{20\}\|TELEGRAM_BOT_TOKEN" .

# 3. Absolute deployment paths
grep -rln "/data/data/com.termux\|/storage/emulated" .

# 4. Credential files
find . -name ".env*" -o -name "*.key" -o -name "*.pem"

# 5. Git metadata inside shipped dirs
find . -name ".git" -type d
```

All five checks must return empty before the repository is pushed.