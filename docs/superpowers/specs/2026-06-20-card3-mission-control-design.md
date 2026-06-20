# Card 3 — Mission Control: Design Spec

**Date:** 2026-06-20
**Owner:** Laura Myers (Mission Control / integration captain)
**Branch:** `mission`

## Goal

Complete Card 3 of the AI CMO hackathon: take an approved post all the way
through distribution and measurement, then run a recommend-only ads agent behind
a human spend gate. Two human decisions (content approval, ad spend approval)
both happen on one Flask board. `db.py` is the frozen contract and is never
changed.

## Pipeline owned by Card 3

```
qc_review --(human Approve)--> approved --> scheduled --> published --> analyzed
        --> ad_recommended --(human Approve spend)--> ad_approved --> ad_live
```

Off-ramps already handled by the existing gate: `needs_revision`, `rejected`.

## Key decisions (from brainstorm)

1. **Click drives the rest.** Tapping Approve on the board triggers the
   downstream pipeline automatically; it pauses again at the ad spend gate.
2. **Smart stubs, demo-safe.** No live API keys anywhere. Stubs are believable
   (realistic URLs, varied metrics, a real winner score) but cannot fail live.
3. **Ads brain = formula + Claude rationale with fallback.** A real scoring
   formula decides the winner; a short Claude call writes the human-readable
   recommendation; a templated fallback runs if no API key is present.
4. **Synchronous driver (option A).** The schedule→publish→analyze chain runs
   inline before the board page reloads — near-instant with stubs, reliable for
   a live demo. No background threads.

## Architecture

### New component: the pipeline driver

A single function (e.g. `engine/mission/driver.py: drive(post_id)`) that runs
the downstream mission stations in order until it reaches the next human stop:

```
drive(post_id):  schedule.run -> publish.run -> analytics.run -> ads_agent.run
```

`ads_agent.run` stamps `ad_recommended` and stops (no auto spend), so the driver
naturally halts at the spend gate. Both `run.py` (auto demo, `auto_approve=True`)
and the Flask board's Approve handler call the same driver — one code path, two
front doors. This avoids pipeline logic drifting between the two entry points.

### Stations (all keep `run(post_id, auto_approve=False)`)

**`schedule.py`** — pick a believable next slot from a small per-platform
best-time table (e.g. LinkedIn → next weekday 09:00; Instagram → next day 11:00),
rolled forward to the next future occurrence. Set `scheduled_for`, advance to
`scheduled`. No external calls.

**`publish.py`** — log a realistic publish and write a platform-shaped
`published_url` (e.g. `https://linkedin.com/posts/lumen-skin-<short-id>`).
Advance to `published`. Structured so a real Zernio call could replace the body
later, but the floor needs no key.

**`analytics.py`** — generate varied, plausible metrics derived deterministically
from the post id (stable within a run, realistic ratios), in the contract's JSON
shape: `likes, comments, shares, follows, impressions`. Advance to `analyzed`.

**`ads_agent.py`**
1. **Winner score** — real formula: engagement rate
   `(likes+comments+shares)/impressions` plus follows-per-impression, combined
   into a 0–100 score vs a threshold (`WINNER_THRESHOLD = 30`, calibrated so the
   majority of generator-produced posts clear it). Replaces the naive
   `follows > 10`. A demo override (`DEMO_FORCE_WINNER=1` env var, or the magic
   word `demowin` in the seed idea) guarantees the ad path fires on stage.
2. **Recommendation** — propose budget + audience; a short Claude call writes the
   "why this won / who to target / suggested spend" rationale shown on the spend
   gate. Templated fallback when no API key.
3. **Ad assembly** — call Brain's ad-copy fn and Studio's ad-creative render
   *if present*; otherwise fall back to the post's own hook/body/image. Card 3
   must work whether or not those teammate functions have landed.
4. Advance to `ad_recommended`, store `ad_budget`, `ad_audience`, `ad_status`,
   and the rationale, then stop.
5. After human spend approval: advance to `ad_approved`
   (`ad_spend_approved_by`), run a stub pusher (believable campaign id, no real
   Meta/LinkedIn call), advance to `ad_live`.

### Board (`gate.py`) — extend, don't rewrite

- Keep the existing `qc_review` **Approvals** section and styling.
- Approve handler: stamp `approved`, then call `drive(post_id)`.
- New **Spend approvals** section listing `ad_recommended` posts: shows ad
  creative, proposed budget/audience, Claude rationale, with **Approve spend /
  Decline** buttons.
- New `/spend/<id>` handler: Approve → `ad_approved` → pusher → `ad_live`;
  Decline → record via `ad_status` (post stays put, no spend).
- Stays phone-friendly and on-brand.

### `run.py`

Replace the hand-rolled loop with a call to the shared driver (after Brain +
Studio + gate auto-approve) so auto-demo and human-demo share one path. Stays
green with stubs and the standard library.

## Testing

- **Full-loop pytest** (temp DB, `auto_approve=True`): post reaches `ad_live`
  with all fields populated.
- **Not-a-winner test:** low-engagement metrics → ads agent does nothing, post
  rests at `analyzed`.
- **Gate route tests:** simulate Approve click → post walks forward; simulate
  Approve-spend → `ad_live`.
- **Manual smoke:** `python run.py "..."` green; launch board, click both gates
  live.

## Integration notes

All changes stay inside `engine/mission/`, `engine/ads/`, `run.py`. `db.py`
untouched. Brain/Studio ad functions are called defensively. Merges of `brain` +
`studio` + `mission` stay conflict-free.

## Out of scope (YAGNI for today)

- Real Zernio / Meta / LinkedIn API calls.
- Background threading / job queue.
- Notion mirror of the gate.
- Real-time analytics polling.
