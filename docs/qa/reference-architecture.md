# Reference Architecture and Named-Integration Register

This is the QA source of truth for the AI CMO team build. It exists so QA can audit
named tools, not just abstract shapes.

## Why this file exists

A tool-agnostic spec describes shapes ("a render backend", "a publishing API")
but never names the actual tools. A QA pass that audits the code against a
tool-agnostic spec is structurally blind: it can confirm "a render backend
exists" but has no line item saying "Playwright specifically should be wired", so
a real, named tool that the source describes but the code never wires is
invisible to it. That is the class of miss that hides an integration in plain
sight.

The Named-Integration Register below closes that gap. Every concrete external
tool the system uses or that the source materials name gets one row, with the
exact env var that gates it and its real status in code. Any new external
integration must be added here. A QA pass checks every WIRED row against the repo
to confirm the module exists and is gated, and confirms every STUB-ONLY and NOT
BUILT row is a known gap rather than a silent miss.

## This is a team scaffold

Most rows below are STUB-ONLY or NOT BUILT on purpose. This repo is the starting
point for the hackathon team build: each station ships as a deterministic offline
stub so the whole loop runs end to end with no keys, and each builder replaces
their stub with the real, credential-gated integration. The register tells every
builder, at a glance, which env var their station actually reads and where the
docs currently disagree with the code, so nobody wastes time setting a key the
code ignores.

## The frozen contract

`db.py` at the repo root is THE FROZEN CONTRACT. It defines the status pipeline,
the `posts` schema, and the helpers every station imports (`create_post`,
`get_post`, `update_post`, `advance`, `list_by_status`). It is frozen: all
builders must agree before any change. Do not modify it to make a station pass.

## Named-Integration Register

Status values: WIRED (real client, credential-gated, with an offline fallback),
STUB-ONLY (referenced or declared, but the code path is a deterministic stub or a
TODO placeholder with no real client), NOT BUILT (named in source but no module
or code at all).

| Tool | Function | Env seam | Stub/offline behavior | Status in code |
|---|---|---|---|---|
| Notion | Mirror the pipeline to a client-facing board and pull human approve/reject decisions back. | `NOTION_TOKEN` (read in `engine/dashboard/notion_client.py`), `NOTION_PARENT_PAGE_ID` (read in `engine/dashboard/notion_provision.py`) | `is_configured()` False runs fully offline: writes the JSON board `outputs/notion-mirror.json` with a stub database id. Token set but `NOTION_PARENT_PAGE_ID` missing fails loud rather than pretending. | WIRED |
| DataForSEO | Optional Voice of Customer enrichment: real query phrasing for pain points. | DataForSEO client is dependency-injected into `engine/brain/voc.py`; docs name `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` | The client defaults to None and the offline deterministic VoC signal from client-data files always stands. No network unless a configured client is injected. No DataForSEO client module exists in `engine/` yet, only the injection seam. | STUB-ONLY |
| Anthropic (Claude) text generation | Brain Brick chain: seed to pillar, angle, hook, body. | `.env.example` names `ANTHROPIC_API_KEY`, but no engine code reads it. | `engine/brain/generate.py` is a deterministic offline stand-in (parses pillars, audience, voice from client-data files). No `import anthropic`, no API call. Real generation is delegated to the `/ai-cmo-generate` Claude Code command, not Python. | STUB-ONLY |
| Claude vision (brand QC) | Score the rendered image 0 to 100 against the brand spec and gate. | Docs name `AICMO_VISION_QC=claude`, but that string appears in no code. | `engine/studio/brand_qc.py` hardcodes a passing score and notes the vision QC is not run. TODO(builder) placeholder. | STUB-ONLY |
| Playwright | Screenshot the filled HTML template to a 1080x1350 PNG. | Docs name `AICMO_RENDER=playwright`, but that string appears in no code. | `engine/studio/render.py` sets the image path but produces no file. TODO(builder) placeholder. Playwright is in `requirements.txt` as a real-build-only dependency. | STUB-ONLY |
| Zernio | Publish the post and pull engagement analytics. | Docs name `ZERNIO_API_KEY`, but no code reads it; the `engine/mission/zernio.py` wrapper named in the plan does not exist. | `engine/mission/publish.py` writes a fake post URL; `engine/mission/analytics.py` writes hardcoded mock metrics. Both carry TODO(builder). | STUB-ONLY |
| Meta Ads | Push an approved ad to a live campaign. | Canonical `META_ACCESS_TOKEN` (README and `.env.example` agree). Code reads no env var yet; the builder adds the gate when wiring the real push. | `engine/ads/ads_agent.py` hardcodes a fake campaign id. TODO(builder). No `ads_push.py` module yet. | STUB-ONLY |
| LinkedIn Ads | Alternate ad platform push. | Canonical `LINKEDIN_ACCESS_TOKEN` (README and `.env.example` agree). Code reads no env var yet; the builder adds the gate when wiring the real push. | Same inline fake-campaign stub as Meta in `engine/ads/ads_agent.py`. No distinct LinkedIn code path. | STUB-ONLY |
| GSC (Google Search Console) | Intelligence-layer search-console signals. | Named in docs only. No env read, no client module. | No code at all. Pure documentation intent. | NOT BUILT |
| Apify | Intelligence-layer competitor scrapes. | `APIFY_TOKEN` named in docs only. No env read, no client module. | No code at all. Pure documentation intent. | NOT BUILT |

## Doc-vs-code mismatches to resolve while building

These are not bugs in the loop (the loop runs offline regardless), but they will
silently waste a builder's time, because setting the documented key activates
nothing.

1. Meta Ads: `.env.example` and README now agree on the canonical `META_ACCESS_TOKEN`, but the code still reads no env var. The builder adds the gate when wiring the real campaign push.
2. LinkedIn Ads: `.env.example` and README now agree on `LINKEDIN_ACCESS_TOKEN`, but the code still reads no env var. Same: add the gate when wiring the real push.
3. Anthropic: `.env.example` declares `ANTHROPIC_API_KEY`, but no Python reads it (generation lives in a Claude Code command). Either wire a Python seam or note in the docs that the key is for the command, not the engine.
4. Render and vision QC: README documents `AICMO_RENDER=playwright` and `AICMO_VISION_QC=claude` as the go-real switches, but neither string exists in code. The stations are unconditional stubs. Add the env check when wiring the real path.
5. Zernio: `ZERNIO_API_KEY` is documented in two places, but no code reads it and the `zernio.py` wrapper does not exist.

The only env vars the engine actually honors today are `NOTION_TOKEN`,
`NOTION_PARENT_PAGE_ID`, and the injected DataForSEO gate.

## Maintenance

This register is part of the QA source of truth. Any new external integration
must be added here. The source-reconciliation auditor
(`.claude/agents/qa/source-reconciliation-auditor.md`) re-runs whenever the
architecture or an integration changes, and confirms every concrete tool named
in the source has a home in this register. Run it after any station moves from
STUB-ONLY to WIRED.
