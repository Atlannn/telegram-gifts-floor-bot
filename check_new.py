#!/usr/bin/env python3
"""Fast check for new gift collections: one request to fragment.com/gifts, post anything unseen.

Meant to run every 15 minutes in GitHub Actions. Shares state.json with bot.py, so a collection is
announced once, by whichever job sees it first. The post carries a picture of the cheapest lot.
Standard library only.

    python check_new.py --dry-run
"""
import argparse
import os
import re
import sys

import bot

SLUG_RE = re.compile(r'href="/gifts/([a-z0-9]+)')
MIN_LIST = 50   # a shorter list means the page changed or failed: do not trust it
MAX_NEW = 5     # more than this at once looks like a parsing change, not new gifts


def parse_slugs(page):
    return sorted(set(SLUG_RE.findall(page)))


def fetch_slugs():
    return parse_slugs(bot.http_get(f"{bot.FRAGMENT}/gifts"))


def plan(slugs, state):
    """Return (new_slugs, new_state, error). Never announces on a suspicious list."""
    known = set(state["known"])
    if len(slugs) < MIN_LIST:
        return [], state, f"only {len(slugs)} collections on the page, ignoring"
    if not known:
        return [], {**state, "known": slugs}, None   # first run: just remember
    new = sorted(set(slugs) - known)
    if len(new) > MAX_NEW:
        return [], state, f"{len(new)} new collections at once, looks like a page change, ignoring"
    if not new:
        return [], state, None
    return new, {**state, "known": sorted(known | set(new))}, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    state = bot.load_state()
    try:
        slugs = fetch_slugs()
    except Exception as e:   # Fragment hiccup: warn, do not fail the run
        print(f"::warning::cannot read the gifts page: {e}")
        return 0
    new_slugs, new_state, error = plan(slugs, state)
    if error:
        print(f"::warning::{error}")   # a warning, not a failure: Fragment hiccups should not email the owner
        return 0
    names = bot.fetch_names() if new_slugs else {}
    posts = []
    for slug in new_slugs:
        lot = bot.fetch_lot(slug)
        posts.append(((lot or {}).get("image"), bot.new_gift_message(slug, names, lot)))
    if args.dry_run:
        print("\n\n---\n\n".join(f"[photo: {p}]\n{t}" if p else t for p, t in posts) or "(no new collections)")
        return 0
    token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if posts and not (token and chat):
        print("error: set TG_BOT_TOKEN and TG_CHAT_ID", file=sys.stderr)
        return 1
    for photo, text in posts:
        if photo:
            bot.send_photo(token, chat, photo, text)
        else:
            bot.send(token, chat, text)
    if new_state != state:
        bot.save_state(new_state)
    print(f"announced {len(posts)} new collection(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
