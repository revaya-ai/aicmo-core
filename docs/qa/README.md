# QA, How this build is checked

This build is checked against its source materials, not just against itself. The
principle: a QA pass that audits the code against an incomplete spec still ships
an incomplete system. So the spec itself gets audited against the source.

## The source of truth

`reference-architecture.md` is the QA source of truth, and its centerpiece is the
Named-Integration Register: one row per external tool, with the exact env var
that gates it and its real status in code (WIRED, STUB-ONLY, or NOT BUILT). This
is a team scaffold, so most rows are STUB-ONLY or NOT BUILT by design. Each
builder replaces their station's stub with the real, credential-gated
integration and flips the row to WIRED.

## The auditor

`.claude/agents/qa/source-reconciliation-auditor.md` is the standing auditor. It
audits the spec against the source: it confirms every concrete tool, channel,
pipeline step, and named behavior in the source materials has a home in the
register, and it flags doc-vs-code mismatches (an env var the docs name but the
code never reads). It is run by an agent that did not make the change under audit.

Re-run it whenever the architecture or an integration changes, especially when a
station moves from STUB-ONLY to WIRED. It writes a fresh report to `reports/`.

## Audit trail

`reports/source-reconciliation.md` is the latest audit output, kept as the
record. The baseline run flagged five doc-vs-code env-var mismatches for the
builders to resolve as they wire real integrations.
