# AI CMO — Handoff Guide

**For agency owners taking this away to use on their own clients.**

> The big idea (Jamie's method): don't guess which content to pay for. Post organically,
> measure which posts brought **follows**, and put ad budget only behind the **top 2–3**.
> You're testing free ads, then paying to scale the proven winners.

See `system-diagram.png` for the visual.

---

## How the system works — 10 stages

| # | Stage | What happens | Runs where |
|---|-------|--------------|-----------|
| 1 | **Brand Context** | The client's brand files (voice, audience, offers). Set up once per client. | Local |
| 2 | **Brain** | Writes the post in the client's voice. | 🔌 Claude API |
| 3 | **Studio** | Renders the image (1080×1350) and brand-checks it with vision. | 🔌 Claude API |
| 4 | **Human Gate ✋** | A person approves / revises / rejects the post. | Local web page |
| 5 | **Publish** | Posts/schedules to Instagram. | 🔌 Zernio + IG |
| 6 | **Measure** | Pulls **follows per post** back. | 🔌 Zernio / IG |
| 7 | **Winner Engine** | Ranks every post by follows, picks the **top 2–3**. | Local |
| 8 | **Human Gate ✋** | A person approves the ad spend (budget + audience). | Local web page |
| 9 | **Paid Ads** | Runs ads on the winners only. | 🔌 Meta Ads |
| 10 | **Live + Feedback** | Ad goes live; results feed back into the next round. | 🔌 Meta / IG |

---

## What you need to plug in (and where)

By default the system runs in **dry-run mode** — it shows exactly what it *would* post and
spend, with **no accounts and no money**. To take it live, connect these:

| Tool | What it powers | Where to get it | What to do |
|------|----------------|-----------------|-----------|
| **Anthropic (Claude) API key** | Brain (writing) + Studio (image check) | console.anthropic.com → API Keys | Paste into `.env` as `ANTHROPIC_API_KEY` |
| **Instagram Business/Creator account** | Posting + follows data | instagram.com → settings → switch to Professional | Needed for publish + ads |
| **Facebook Page + Meta Business Suite** | Required for IG publishing, analytics, ads | business.facebook.com | Connect your IG account to the Page |
| **Zernio account + API key** | Publishing/scheduling + pulling analytics | zernio.com | Connect IG/Meta inside Zernio; paste `ZERNIO_API_KEY` into `.env` |
| **Meta Ads account** | Running the paid ads | business.facebook.com → Ads Manager | Add a payment method; connect the ad account |
| **Placid** *(optional)* | Nicer templated graphics | placid.app | Paste `PLACID_API_KEY` into `.env` (optional) |

**The one file that holds all the keys:** `.env` (copy `.env.example` → `.env` and fill it in).
Every key is optional — leave one blank and that stage stays in dry-run.

### The honest order of difficulty
1. **Anthropic key** — 5 minutes, instant. Unlocks real content + image checks. *Do this first.*
2. **Instagram Business + Facebook Page** — 15–20 minutes of Meta setup.
3. **Zernio** — sign up, connect your IG/Meta.
4. **Meta Ads** — ad account + payment method. Some ad permissions need Meta app review (can take days), so **plan ahead** if you want live ads.

---

## Run it

```bash
# 1. one-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then add your keys (or leave blank for dry-run)

# 2. onboard a client (creates their brand files)
#    /ai-cmo-onboard   (or copy client-data/lumen-skin and edit)

# 3. run the whole loop on one idea
python run.py "your content idea here"

# 4. open the human board to approve content + ad spend
python engine/mission/gate.py      # → http://localhost:5050
```

Dry-run by default. Add keys to `.env` to switch stages live, one at a time.
