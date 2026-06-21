"""STATION 3 — Mission: publish a scheduled post.

Reads:  status == scheduled   (uses image_path, hook, body, platform)
Writes: status == published   (sets published_url)

Signature: run(post_id: str, auto_approve: bool = False) -> None

The real version pushes the post + image to Zernio (or the platform API) and
records the live URL. The stub logs and sets a fake published_url.
"""

import engine.env  # noqa: F401
from db import Status, get_post, advance


# Where each platform's posts "live". Floor = demo-safe; swap in a real Zernio
# call here later without changing the contract.
PLATFORM_BASE = {
    "linkedin": "https://linkedin.com/posts",
    "instagram": "https://instagram.com/p",
    "x": "https://x.com/lumen-skin/status",
}
DEFAULT_BASE = "https://social.test/posts"


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)
    platform = post["platform"]
    base = PLATFORM_BASE.get(platform, DEFAULT_BASE)
    slug = f"lumen-skin-{post_id[:8]}"
    published_url = f"{base}/{slug}"

    print(f"    [publish] posted to {platform}: {published_url}")
    advance(post_id, Status.PUBLISHED, published_url=published_url)
