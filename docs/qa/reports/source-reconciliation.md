# Source Reconciliation Report

Independent reconciliation of the source materials against
`docs/qa/reference-architecture.md` and its Named-Integration Register. Read-only
audit, nothing modified. This is the baseline run, captured when the register was
first added to this repo.

## Verdict

PASS on register completeness, with five doc-vs-code mismatches flagged for the
builders to resolve as they wire real integrations.

Every concrete external tool named in the source materials now has a row in the
Named-Integration Register. The register honestly reflects that this is a team
scaffold: one integration is WIRED, six are STUB-ONLY by design, and two are NOT
BUILT.

## Register status summary

| Tool | Status | Note |
|---|---|---|
| Notion | WIRED | Only genuinely wired integration. Real stdlib client, gated on `NOTION_TOKEN` plus `NOTION_PARENT_PAGE_ID`, offline JSON-board fallback, fails loud when half-configured. |
| DataForSEO | STUB-ONLY | Injection seam in `engine/brain/voc.py`; no client module in `engine/` yet. Offline VoC signal always stands. |
| Anthropic (Claude) text gen | STUB-ONLY | `engine/brain/generate.py` is a deterministic stand-in. Real generation lives in the `/ai-cmo-generate` command, not Python. No SDK call in the engine. |
| Claude vision (brand QC) | STUB-ONLY | `engine/studio/brand_qc.py` hardcodes a passing score. TODO(builder). |
| Playwright | STUB-ONLY | `engine/studio/render.py` sets the image path but renders no file. TODO(builder). |
| Zernio | STUB-ONLY | `publish.py` and `analytics.py` carry inline stubs. The `zernio.py` wrapper named in the plan does not exist. |
| Meta Ads | STUB-ONLY | `engine/ads/ads_agent.py` hardcodes a fake campaign id. No env gate yet. |
| LinkedIn Ads | STUB-ONLY | Same inline stub as Meta. No distinct code path. |
| GSC (Google Search Console) | NOT BUILT | Named in docs only. No env read, no module. |
| Apify | NOT BUILT | Named in docs only. No env read, no module. |

## Doc-vs-code env-var mismatches (the bug class this audit exists to catch)

The only env vars the engine actually honors are `NOTION_TOKEN`,
`NOTION_PARENT_PAGE_ID`, and the injected DataForSEO gate. Every other documented
key is currently inert. Each mismatch below will silently waste a builder's time,
because setting the documented key activates nothing.

1. Meta Ads: README names `META_ACCESS_TOKEN`, `.env.example` names `META_ADS_TOKEN`, code reads neither. Pick one canonical name, add the env gate, align both docs.
2. LinkedIn Ads: README names `LINKEDIN_ACCESS_TOKEN`, `.env.example` names `LINKEDIN_ADS_TOKEN`, code reads neither. Same fix.
3. Anthropic: `.env.example` declares `ANTHROPIC_API_KEY`, but no Python reads it (generation lives in a Claude Code command). Wire a Python seam or document that the key is for the command, not the engine.
4. Render and vision QC: README documents `AICMO_RENDER=playwright` and `AICMO_VISION_QC=claude` as the go-real switches, but neither string exists in code. The stations are unconditional stubs. Add the env check when wiring the real path.
5. Zernio: `ZERNIO_API_KEY` is documented in two places, but no code reads it and the `zernio.py` wrapper does not exist.

## Named in source but no code at all (genuine NOT BUILT gaps)

- `engine/mission/zernio.py` (named in the build plan; publish and analytics stub inline instead).
- `engine/ads/ads_push.py` (named in the plan; push logic lives inline in `ads_agent.py`).
- A DataForSEO client module under `engine/` (the injection seam exists in `voc.py`, the module does not).
- GSC and Apify clients (named in docs only).

## The frozen contract

`db.py` is present at the repo root, self-described as THE FROZEN CONTRACT. It
defines the status pipeline, the `posts` schema, and the helpers every station
imports. Treat it as frozen: do not modify it to make a station pass.

## Trustworthiness statement

With the Named-Integration Register in place, `reference-architecture.md` is a
trustworthy QA source of truth for named tools: every tool the source describes
has a row, and each row states its real code status and the env var the code
actually reads. The register must be re-reconciled against the source whenever a
station moves from STUB-ONLY to WIRED, by an agent that did not make that change.
