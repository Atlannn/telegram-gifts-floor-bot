#!/usr/bin/env python3
"""Post the daily Telegram-gifts floor summary and new collections to a Telegram channel.

Reads the open dataset https://github.com/Atlannn/telegram-gifts-floor-price (one CSV request),
compares the latest day with the previous one and posts through the Telegram Bot API.
Standard library only. Secrets come from the environment, never from files:

    TG_BOT_TOKEN   token from @BotFather
    TG_CHAT_ID     channel, e.g. @my_channel (the bot must be an admin of it)

    python bot.py --dry-run      # print the messages, send nothing
    python bot.py                # send (skips a day that was already posted)
"""
import argparse
import csv
import datetime as dt
import html
import io
import json
import os
import sys
import urllib.parse
import urllib.request

CSV_URL = "https://raw.githubusercontent.com/Atlannn/telegram-gifts-floor-price/main/data/floor_prices.csv"
SITE_URL = "https://balticassets.eu/en/crypto/telegram-gifts/"
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
UA = "telegram-gifts-floor-bot/0.1 (+https://github.com/Atlannn/telegram-gifts-floor-bot)"

MIN_CHANGE = 10.0   # percent, smallest day-over-day move worth a line
MIN_PRICE = 20.0    # GRAM, ignore cheap gifts where 2 GRAM looks like +40%
TOP_N = 5


def num(v):
    return float(v) if v not in ("", None) else None


def fmt(x):
    return f"{x:,.0f}".replace(",", " ") if x >= 100 else f"{x:g}"


def link(slug):
    return f'<a href="https://fragment.com/gifts/{slug}">{html.escape(slug)}</a>'


def parse_rows(text):
    """{date: {collection: {"floor", "fixed"}}} from the dataset CSV."""
    days = {}
    for r in csv.DictReader(io.StringIO(text)):
        days.setdefault(r["date"], {})[r["collection"]] = {
            "floor": num(r["floor_gram"]), "fixed": num(r["floor_fixed_gram"])}
    return days


def movers(today, prev):
    """(up, down): lists of (slug, now, was, pct) on fixed-price floors, biggest first."""
    moves = []
    for slug, t in today.items():
        p = prev.get(slug)
        if not p or t["fixed"] is None or p["fixed"] is None or p["fixed"] <= 0:
            continue
        if max(t["fixed"], p["fixed"]) < MIN_PRICE:
            continue
        pct = (t["fixed"] - p["fixed"]) / p["fixed"] * 100
        if abs(pct) >= MIN_CHANGE:
            moves.append((slug, t["fixed"], p["fixed"], pct))
    up = sorted((m for m in moves if m[3] > 0), key=lambda m: -m[3])[:TOP_N]
    down = sorted((m for m in moves if m[3] < 0), key=lambda m: m[3])[:TOP_N]
    return up, down


def daily_message(date, today, prev):
    d = dt.date.fromisoformat(date)
    lines = [f"<b>Telegram gifts floor prices, {d.day} {d.strftime('%b %Y')}</b>", ""]
    top = sorted(((s, v) for s, v in today.items() if v["floor"] is not None),
                 key=lambda sv: -sv[1]["floor"])[:5]
    lines.append("<b>Highest floors (GRAM)</b>")
    for slug, v in top:
        note = "" if v["fixed"] is not None else " (auction price, no fixed-price lot)"
        lines.append(f"{link(slug)}: {fmt(v['floor'])}{note}")
    if prev:
        up, down = movers(today, prev)
        for title, items, sign in (("Up since yesterday", up, "+"), ("Down since yesterday", down, "")):
            if items:
                lines += ["", f"<b>{title}</b>"]
                lines += [f"{link(s)}: {fmt(now)} (was {fmt(was)}, {sign}{pct:.0f}%)"
                          for s, now, was, pct in items]
        if not up and not down:
            lines += ["", f"No fixed-price floor moved by {MIN_CHANGE:.0f}% or more."]
    lines += ["", "Floor = cheapest lot on Fragment, an asking price, fees not included. "
              f'<a href="{SITE_URL}">Rarity and profit calculator</a>']
    return "\n".join(lines)


def new_gift_message(slug, v):
    price = ""
    if v["floor"] is not None:
        price = f"\nFloor: {fmt(v['floor'])} GRAM" + ("" if v["fixed"] is not None else " (auction price)")
    return (f"<b>New gift collection on Fragment: {link(slug)}</b>{price}\n"
            f'<a href="{SITE_URL}">Telegram Gifts checker</a>')


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"known": [], "last_posted": None}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=1)
        f.write("\n")


def plan(days, state):
    """Return (messages, new_state). First run only seeds the state and posts nothing."""
    date = max(days)
    today = days[date]
    earlier = [d for d in days if d < date]
    prev = days[max(earlier)] if earlier else {}
    known = set(state["known"])
    if state["last_posted"] == date:
        return [], state
    new_state = {"known": sorted(known | set(today)), "last_posted": date}
    if not known:  # first run: remember everything, do not announce 120 "new" gifts
        return [], new_state
    messages = [daily_message(date, today, prev)]
    messages += [new_gift_message(s, today[s]) for s in sorted(set(today) - known)]
    return messages, new_state


def send(token, chat_id, text):
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data,
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if not json.load(r).get("ok"):
            raise RuntimeError("Telegram refused the message")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print messages, send nothing, keep state")
    ap.add_argument("--test", action="store_true", help="send one test message to the channel and exit")
    args = ap.parse_args(argv)
    if args.test:
        token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
        if not (token and chat):
            print("error: set TG_BOT_TOKEN and TG_CHAT_ID", file=sys.stderr)
            return 1
        send(token, chat, "Test message: the bot is connected. Daily floor summaries start tomorrow.")
        print("test message sent")
        return 0
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        days = parse_rows(r.read().decode("utf-8"))
    state = load_state()
    messages, new_state = plan(days, state)
    if args.dry_run:
        print("\n\n---\n\n".join(messages) if messages else "(nothing to post)")
        return 0
    token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if messages and not (token and chat):
        print("error: set TG_BOT_TOKEN and TG_CHAT_ID", file=sys.stderr)
        return 1
    for m in messages:
        send(token, chat, m)
    save_state(new_state)
    print(f"posted {len(messages)} message(s) for {new_state['last_posted']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
