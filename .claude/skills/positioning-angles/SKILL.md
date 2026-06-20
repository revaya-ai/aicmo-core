---
name: positioning-angles
description: Named angle library for the AI CMO. Loaded by the content-os Angle step to pick a deliberate take for a topic instead of defaulting to a generic one. Returns one named angle plus a one-line reason it fits this audience and pillar.
---

# positioning-angles

## Purpose

A topic is not a post. The angle is the specific take that makes a topic land for a specific reader. The content-os Brick chain loads this skill at the Angle step, after the topic and pillar are locked, and before the hook is written.

## What an angle is

The angle answers: "Of all the ways to say this, which one creates tension this reader feels?" It is chosen against the client audience (read brand-and-audience first) and the pillar already locked in the topic step.

## Named angle library

Pick one. Each is reusable across topics.

- **The Simpler Truth**: the honest, less complicated version of a thing people overcomplicate.
- **The Hidden Cost**: the real price of the status quo the reader has not counted.
- **The Myth Correction**: name a common belief, show why it is wrong, give the fix.
- **The Insider View**: what people who actually do this know that outsiders do not.
- **The Contrarian Take**: the defensible opposite of the popular advice.
- **The Origin Lesson**: a specific moment or mistake that taught the lesson, told plainly.
- **The Cost Of Doing Nothing**: what keeps getting worse while the reader waits.
- **The Permission Slip**: telling the reader they are allowed to stop doing the exhausting thing.
- **The Quiet Win**: the small, unglamorous habit that beats the flashy one.
- **The Comparison**: two paths side by side, with the honest tradeoff named.

## How to choose

1. Read the primary audience and what turns them off.
2. Find the tension between what they want and what they have been told.
3. Pick the angle that names that tension most directly for this pillar.
4. If two fit, pick the one that lets you back it with a specific the brand can actually prove.

## Output

Return two lines:
- Angle: <one named angle from the library>
- Why: <one sentence on why it fits this audience and pillar>
