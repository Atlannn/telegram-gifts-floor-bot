#!/usr/bin/env python3
"""Fast check for new gift collections: one request to fragment.com/gifts, post anything unseen.

Meant to run every 15 minutes in GitHub Actions. Shares state.json with bot.py, so a collection is
announced once, by whichever job sees it first. Standard library only.

    python check_new.py --dry-run
"""
import argparse
import os
import re
import sys
import urllib.request

import bot

GIFTS_URL = "https://fragment.com/gifts"
SLUG_RE = re.compile(r'href="/gifts/([a-z0-9]+)')
MIN_LIST = 50   # a shorter list means the page changed or failed: do not trust it
MAX_NEW = 5     # more than this at once looks like a parsing change, not new gifts


def parse_slugs(page):
    return sorted(set(SLUG_RE.findall(page)))


def fetch_slugs():
    req = urllib.request.Request(GIFTS_URL, headers={"User-Agent": bot.UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return parse_slugs(r.read().decode("utf-8", "replace"))


def message(slug):
    return (f"<b>New gift collection on Fragment: {bot.link(slug)}</b>\n"
            f'<a href="{bot.SITE_URL}">Telegram Gifts checker</a>')


def plan(slugs, state):
    """Return (messages, new_state, error). Never announces on a suspicious list."""
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
    return [message(s) for s in new], {**state, "known": sorted(known | set(new))}, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    state = bot.load_state()
    messages, new_state, error = plan(fetch_slugs(), state)
    if error:
        print(f"::warning::{error}")   # a warning, not a failure: Fragment hiccups should not email the owner
        return 0
    if args.dry_run:
        print("\n\n---\n\n".join(messages) if messages else "(no new collections)")
        return 0
    token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if messages and not (token and chat):
        print("error: set TG_BOT_TOKEN and TG_CHAT_ID", file=sys.stderr)
        return 1
    for m in messages:
        bot.send(token, chat, m)
    if new_state != state:
        bot.save_state(new_state)
    print(f"announced {len(messages)} new collection(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
