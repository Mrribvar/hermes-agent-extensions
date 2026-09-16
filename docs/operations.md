# Operational Tooling

**Location:** `skills/`, plus scripts kept outside the repository.
**Ownership:** Custom.
**Runtime:** Active (skills).

## Original skills

Three original skills ship with this repository. They are self-contained
Markdown + (for one of them) stdlib-only Python.

### `skills/persian-writing/`

A complete toolkit for producing natural, well-formed Persian (Farsi):

- Register detection and writing style guidance.
- Persian orthography rules (ZWNJ / نیم‌فاصله, digit and punctuation rules).
- Right-to-left document layout for Word, PDF, PowerPoint, HTML, Excel, and
  images.
- SEO and copywriting guidance for a Persian audience.
- Deterministic scripts: cleanup (`persian_cleanup.py`), lint
  (`fa_lint.py`), PDF verification (`verify_pdf.py`), font installation
  (`install_fonts.sh`).
- Bundled fonts (Vazirmatn and Lalezar, SIL Open Font License).

The skill is harness-neutral — it names specific tools as examples rather than
limits, and the rules it enforces in code are also stated in prose in its
references.

### `skills/reelo/`

A cycle for turning an existing video into a reel:

1. Fetch the video (YouTube / Instagram).
2. Extract subtitles.
3. Run a ten-role think tank (chief content officer, copywriter, editor, data
   analyst, …).
4. Analyze the source video.
5. Write the reel script.
6. **Produce a mandatory edit plan** (`08_EDIT_PLAN.md`) with per-cut source
   timing, exact quotes, and a `paraphrase` label for anything that is not a
   verbatim source quote.
7. Suggest cover titles.
8. Write an image-generation prompt.
9. Write an SEO-optimized caption.

The quote rule is the important part: nothing may be attributed to the speaker
unless the exact sentence exists in the source subtitles.

### `skills/freestyle-docs/`

A reference for when to use Freestyle VMs and when not to: long-running agent
tasks, branching experiments, and multi-tenant isolation are good fits;
short-lived scripts and CI workloads are not.

## Architecture documentation

The `docs/` directory contains:

- `architecture.md`, `governance.md`, `execution-layer.md`,
  `verification-learning.md` — extended walkthroughs.
- Phase reports (`EXECUTION_LAYER_*.md`, `PHASE_*.md`, `PRODUCTION_*.md`,
  `HEALTH_AUDIT_*.md`) — the historical record of the phases documented in
  `CONTRIBUTIONS.md`.

## Scripts — what is not shipped

The development deployment used a set of maintenance scripts under a private
`~/.hermes/scripts/` directory. They are **not** shipped here because they
encode deployment-specific paths, infrastructure details, or private data.

Categories of scripts that were used (described, not included):

- Instagram data refreshers (session-based, GET-only)
- VPN / proxy infrastructure helpers (X-UI, WireGuard, DNS-leak checks)
- Knowledge-graph maintenance (cluster fixing, watchdog)
- Daily and weekly reporting jobs
- Usage tracking and token accounting

If you want a script from any of these categories, the general shape is
described in this document; the deployment-specific version is not appropriate
for a public repository.

## Automation

The development deployment ran a cron fleet of scheduled jobs (morning brief,
Instagram content suggestion, lead-reply draft, data refresh, weekly reports).
The cron configuration itself lives in the Hermes Agent runtime, not in this
repository.

## Design note

Operational tooling follows the same rule as everything else here: it does not
modify upstream Hermes, and it does not add a new core tool. Every automation
is either a cron job or a skill — not a new capability in the agent's tool
schema.