# Contributing

Thanks for your interest in these extensions. A few things to know before you
open a pull request.

## Scope

This repository contains **additive extensions** on top of the upstream
[Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research.
It is not a fork of Hermes Agent, and it does not accept changes to upstream
Hermes Agent code here.

If you have a fix or feature for Hermes Agent itself, please open it against
the upstream project, not against this repository.

## What belongs here

- New extension layers that attach to Hermes Agent through a documented
  boundary (a plugin, a hook, a CLI command + skill, or a service-gated tool).
- Fixes and improvements to the existing extensions.
- New original skills.
- Documentation improvements.

## What does not belong here

- Modifications to upstream Hermes Agent files.
- New credentials, `.env` files, or any secret material.
- VPN configuration or infrastructure artifacts.
- Personal data, memory files, or runtime databases.
- Code that violates the boundary rules below.

## The boundary rules

Every extension in this repository follows three rules. A pull request that
breaks any of them will not be merged.

1. **Additive only.** No upstream file is modified. If you need to change
   upstream behavior, that is a conversation with the upstream maintainers,
   not a change here.
2. **Cache-safe.** Nothing may mutate past conversation context, swap the
   toolset mid-conversation, or rebuild the system prompt. This preserves the
   prompt cache and keeps per-turn cost stable.
3. **Fail-safe.** Every cross-boundary call must be wrapped so a failure
   degrades to `None` / `{}` / `False` and never blocks a turn.

## Status honesty

If you add or change an extension, update `PROJECT_STATUS.md`. Every status
label must be backed by evidence: a file on disk, a test that actually runs,
or an observable runtime trace. If you cannot produce evidence, the label is
`Dormant` or `Not Verified`.

This is the same principle the whole repository is built on:

> **No Evidence = No Claim.**

## Development

Because the extensions import from upstream, development happens inside a
Hermes Agent checkout. See the Development section of `README.md`.

## Tests

Run the tests from inside a Hermes Agent checkout:

```bash
cd /path/to/hermes-agent
python -m pytest /path/to/hermes-agent-extensions/tests/ -q
```

Tests are copied verbatim from where they were written and depend on the
upstream modules they exercise.

## Security

Read `SECURITY.md` before submitting anything. The five pre-publish checks must
return clean for any change that adds files.

## Pull request checklist

- [ ] The change is additive (no upstream file modified).
- [ ] The change is cache-safe.
- [ ] Every cross-boundary call is wrapped in `try/except`.
- [ ] `PROJECT_STATUS.md` is updated if the runtime status changed.
- [ ] The five pre-publish checks in `SECURITY.md` return clean.
- [ ] Tests (if any) pass against a Hermes Agent checkout.

## License

By contributing, you agree that your contributions are licensed under the MIT
License (see `LICENSE`).
