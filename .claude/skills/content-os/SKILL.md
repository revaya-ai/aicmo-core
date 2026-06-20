---
name: content-os
description: The Brick chain. The reasoning method the AI CMO uses to turn one seed idea into one on-brand post. Five locked steps run in order, each producing one artifact the next step depends on. Loaded by the ai-cmo-generate command.
---

# content-os

## Purpose

A good post is a chain of deliberate decisions, not a guess. The Brick chain forces five decisions in order and locks each one before the next. The output is four artifacts (pillar, angle, hook, body) handed to ai-cmo-generate for persistence.

## Before you start

Read the client context first:
- `client-data/<client>/strategy.md` for the content pillars and cadence rules.
- `client-data/<client>/brand-and-audience.md` for the audience and what turns them off.
- `client-data/<client>/voice.md` for how the brand sounds.

## The steps (run in order, lock each before the next)

### Phase 0: Voice of Customer
Run before Intake. The source materials start the chain here, not at the seed idea. Load `engine/brain/voc.py` (`voice_of_customer(client, seed_idea)`). It reads the client context (brand-and-audience.md, strategy.md) and returns the audience persona, the real pain points, and the actual phrases customers use. Offline by default and grounded in the loaded context. A configured DataForSEO client may enrich the phrasing, but offline stands on its own. Lock the VoC signal. Every step below references it: Intake restates the seed in the customer's language, Angle targets a real pain point, Hook borrows a real phrase.

### Step 1: Intake
Restate the seed idea in one plain line. Strip it to the single thing it is really about. Lock that line.

### Step 2: Topic and pillar
Write a one-line topic. Name which content pillar it serves, chosen from the client strategy pillars. If it fits no pillar, reshape the topic until it does. Lock the topic and pillar.

### Step 3: Angle
Load the `positioning-angles` skill. Choose one named angle that creates real tension for this audience and pillar. Lock the angle name and a one-line reason.

### Step 4: Hook
Load the `hook-library` skill. Write line one only. Five to ten words. Pick one named hook pattern and fill it with the real topic so it opens an information gap the reader needs closed. No throat-clearing, no "in today's world". Lock the hook.

### Step 5: Story and shift
Load the `story-structures` skill and the `writing-style` skill. First pick one named body arc and outline it in three or four beats. Then write the body to that arc. Run the writing-style self-check. The body is not locked until the self-check passes.

## Locking rules

- Never write the body before the hook is locked.
- Never skip a step. Each step depends on the one before it.
- If a later step exposes a weak earlier decision, go back, fix it, and re-lock forward.

## Output contract

Hand exactly these four locked artifacts to ai-cmo-generate:
- pillar
- angle
- hook
- body

Nothing else. ai-cmo-generate persists them via engine/save_draft.py at status `drafted`.
