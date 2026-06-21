"""
seo_guardrails.py — Copy-review gate for the AI CMO content engine.

Enforces brand voice rules programmatically. Called by the captured-sweep
(Task 5) before a draft can leave the Brain.

Public API:
    score(text: str) -> dict
        Returns {"score": int 0..10, "passed": bool, "failures": list[str]}
        where passed is True when score >= 8.
"""

import re

# 21 banned AI-slop / jargon patterns (from the workspace banned list).
BANNED = [
    "leverage",
    "synergy",
    "streamline",
    "robust",
    "seamless",
    "holistic",
    "ecosystem",
    "best practices",
    "world-class",
    "cutting-edge",
    "revolutionary",
    "game-changer",
    "unlock",
    "delve",
    "deep dive",
    "in today's fast-paced world",
    "it's important to note",
    "rest assured",
    "let me help you",
    "i'd be happy to",
    "at the end of the day",
]

_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
# Match any em dash or en dash that appears anywhere in the text.
_DASH = re.compile(r"[—–]")


def _sentences(text: str) -> list[str]:
    """Split text into non-empty sentences on .!? boundaries."""
    return [s for s in re.split(r"[.!?]\s+", text.strip()) if s]


def _check_no_dashes(text: str) -> bool:
    """Fail if an em dash or en dash appears between words or with surrounding spaces."""
    return not _DASH.search(text)


def _check_no_emoji(text: str) -> bool:
    """Fail if any emoji character is present."""
    return not _EMOJI.search(text)


def _check_no_banned_phrase(text: str) -> bool:
    """Fail if any banned AI-slop / jargon phrase appears (case-insensitive)."""
    low = text.lower()
    return not any(phrase in low for phrase in BANNED)


def _check_no_we_voice(text: str) -> bool:
    """Fail if the word 'we' appears (Shannon writes in first-person singular)."""
    return not re.search(r"\bwe\b", text.lower())


def _check_has_specificity(text: str) -> bool:
    """Pass if at least one digit is present (evidence of concrete numbers)."""
    return bool(re.search(r"\d", text))


def _check_hook_len_ok(text: str) -> bool:
    """Pass if the first sentence is between 5 and 12 words (algorithm-friendly hook)."""
    sentences = _sentences(text)
    if not sentences:
        return False
    return 5 <= len(sentences[0].split()) <= 12


def _check_varied_length(text: str) -> bool:
    """Pass if sentences vary in length (avoids choppy/monotone cadence).

    Measured by bucketing word-counts into groups of 5. If there are 3 or
    fewer sentences we give a pass by default (not enough data to judge).
    """
    sentences = _sentences(text)
    if len(sentences) <= 2:
        return True
    buckets = {len(s.split()) // 5 for s in sentences}
    return len(buckets) > 1


def _check_not_thin(text: str) -> bool:
    """Pass if the text contains at least 25 words (not thin content)."""
    return len(text.split()) >= 25


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_CHECKS = [
    ("no_dashes",        _check_no_dashes),
    ("no_emoji",         _check_no_emoji),
    ("no_banned_phrase", _check_no_banned_phrase),
    ("no_we_voice",      _check_no_we_voice),
    ("has_specificity",  _check_has_specificity),
    ("hook_len_ok",      _check_hook_len_ok),
    ("varied_length",    _check_varied_length),
    ("not_thin",         _check_not_thin),
]


def score(text: str) -> dict:
    """Score a draft against 8 brand-voice / SEO guardrails.

    Returns:
        {
            "score":    int (0-10),
            "passed":   bool (True when score >= 8),
            "failures": list[str]  — names of checks that did not pass
        }
    """
    t = text or ""
    failures = []
    passed_count = 0

    for name, check_fn in _CHECKS:
        if check_fn(t):
            passed_count += 1
        else:
            failures.append(name)

    pts = round(passed_count / len(_CHECKS) * 10)
    return {"score": pts, "passed": pts >= 8, "failures": failures}
