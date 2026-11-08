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
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from emojis import emoji_for

CSV_URL = "https://raw.githubusercontent.com/Atlannn/telegram-gifts-floor-price/main/data/floor_prices.csv"
FRAGMENT = "https://fragment.com"
SITE_URL = "https://balticassets.eu/en/crypto/telegram-gifts/"
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
UA = "Mozilla/5.0 (compatible; telegram-gifts-floor-bot/0.1; +https://github.com/Atlannn/telegram-gifts-floor-bot)"

TOP_N = 5           # lines in each of the Up / Down blocks; no minimum price, no minimum move
CAPTION_LIMIT = 1024  # Telegram limit for a photo caption

NAME_RE = re.compile(r'<a href="/gifts/([a-z0-9]+)"[^>]*>.*?class="tm-main-filters-name">([^<]+)</div>', re.S)
LOT_RE = re.compile(r'<a href="/gift/([a-z0-9]+)-(\d+)[^"]*" class="tm-grid-item">(.*?)</a>', re.S)
LOT_IMG_RE = re.compile(r'<img src="(https://nft\.fragment\.com/gift/[^"]+\.jpg)"')
LOT_NAME_RE = re.compile(r'class="item-name">([^<]+)<')
LOT_PRICE_RE = re.compile(r'icon-ton">([\d,\.]+)</div>')


def num(v):
    return float(v) if v not in ("", None) else None


def pct_str(p):
    return f"{p:.0f}%" if p >= 10 else f"{p:.1f}%"


def fmt(x):
    return f"{x:,.0f}".replace(",", " ") if x >= 100 else f"{x:g}"


def urlopen_retry(req, tries=4):
    """urlopen that retries transient errors (5xx, 429, network) with a growing pause."""
    for i in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429 or i == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) if e.code == 429 else 0
        except urllib.error.URLError:
            if i == tries - 1:
                raise
            wait = 0
        time.sleep(min(max(wait, 5 * 2 ** i), 60))


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return re.sub(r"\s+", " ", r.read().decode("utf-8", "replace"))


def parse_names(page):
    """{slug: display name} from the collection list on fragment.com/gifts."""
    return {slug: html.unescape(name).strip() for slug, name in NAME_RE.findall(page)}


def fetch_names():
    try:
        return parse_names(http_get(f"{FRAGMENT}/gifts"))
    except Exception:  # names are cosmetic: fall back to slugs
        return {}


def label(slug, names):
    return names.get(slug) or slug


def link(slug, names):
    return f'{emoji_for(slug)} <a href="{FRAGMENT}/gifts/{slug}">{html.escape(label(slug, names))}</a>'


def parse_cheapest_lot(page):
    """First lot of a collection page sorted by price: {name, image, price, auction} or None."""
    m = LOT_RE.search(page)
    if not m:
        return None
    block = m.group(3)
    img, name, price = LOT_IMG_RE.search(block), LOT_NAME_RE.search(block), LOT_PRICE_RE.search(block)
    return {
        "name": html.unescape(name.group(1)).strip() if name else None,
        "image": img.group(1) if img else None,
        "price": float(price.group(1).replace(",", "")) if price else None,
        "auction": "js-timer-wrap" in block,
    }


def fetch_lot(slug):
    try:
        return parse_cheapest_lot(http_get(f"{FRAGMENT}/gifts/{slug}?filter=sale&sort=price_asc"))
    except Exception:
        return None


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
        pct = (t["fixed"] - p["fixed"]) / p["fixed"] * 100
        if pct != 0:
            moves.append((slug, t["fixed"], p["fixed"], pct))
    up = sorted((m for m in moves if m[3] > 0), key=lambda m: -m[3])[:TOP_N]
    down = sorted((m for m in moves if m[3] < 0), key=lambda m: m[3])[:TOP_N]
    return up, down


def daily_message(date, today, prev, names=None):
    names = names or {}
    d = dt.date.fromisoformat(date)
    lines = ["<b>Telegram Gifts · Floor Prices</b>", f"{d.day} {d.strftime('%b %Y')}", "",
             "\U0001F3C6 <b>Highest floors</b>"]
    top = sorted(((s, v) for s, v in today.items() if v["floor"] is not None),
                 key=lambda sv: -sv[1]["floor"])[:5]
    for slug, v in top:
        note = "" if v["fixed"] is not None else " (auction)"
        lines.append(f"{link(slug, names)}: <b>{fmt(v['floor'])} GRAM</b>{note}")
    if prev:
        up, down = movers(today, prev)
        for title, items, sign in (("\U0001F4C8 <b>Up in 24h</b>", up, "+"), ("\U0001F4C9 <b>Down in 24h</b>", down, "-")):
            if items:
                lines += ["", title]
                lines += [f"{link(s, names)}: {fmt(now)} GRAM ({sign}{fmt(abs(now - was))} GRAM, {sign}{pct_str(abs(pct))})"
                          for s, now, was, pct in items]
        if not up and not down:
            lines += ["", "<i>No fixed-price floor changed since yesterday.</i>"]
    lines += ["", "<i>Floor = cheapest lot on Fragment, an asking price, fees not included.</i>",
              f'Rarity and profit calculator: <a href="{SITE_URL}">balticassets.eu</a>']
    return "\n".join(lines)


def new_gift_message(slug, names=None, lot=None):
    """Caption/text for a new collection. Uses the cheapest lot's name and price when available."""
    names = names or {}
    title = (lot or {}).get("name") or label(slug, names)
    lines = [f"\U0001F195 <b>New gift collection: {emoji_for(slug)} {html.escape(title)}</b>", ""]
    if lot and lot.get("price") is not None:
        lines.append(f"Floor: <b>{fmt(lot['price'])} GRAM</b>" + (" (auction)" if lot["auction"] else ""))
    lines += [f'<a href="{FRAGMENT}/gifts/{slug}">Open on Fragment</a>',
              f'Rarity and profit calculator: <a href="{SITE_URL}">balticassets.eu</a>']
    return "\n".join(lines)


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
    """Return (date, today, prev, new_slugs, new_state, post_daily).

    First run (empty state) only seeds the state and posts nothing.
    """
    date = max(days)
    today = days[date]
    earlier = [d for d in days if d < date]
    prev = days[max(earlier)] if earlier else {}
    known = set(state["known"])
    if state["last_posted"] == date:
        return date, today, prev, [], state, False
    new_state = {"known": sorted(known | set(today)), "last_posted": date}
    if not known:
        return date, today, prev, [], new_state, False
    return date, today, prev, sorted(set(today) - known), new_state, True


FACTORS = (1.25, 0.78, 1.11, 0.93, 1.42, 0.64, 1.06, 0.87)  # made-up "yesterday / today" ratios for the sample
SAMPLE_NOTE = "<i>SAMPLE POST, please ignore. {}</i>\n\n"


def sample_posts():
    """One of every kind of post, for --test: real floors from the latest day, made-up daily changes."""
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": UA})
    with urlopen_retry(req) as r:
        days = parse_rows(r.read().decode("utf-8"))
    date = max(days)
    today = days[date]
    # yesterday is invented (every fixed-price floor shifted up or down) so that the Up / Down blocks show
    prev = {s: {"floor": v["floor"], "fixed": v["fixed"] and round(v["fixed"] * FACTORS[i % len(FACTORS)], 1)}
            for i, (s, v) in enumerate(sorted(today.items()))}
    names = fetch_names()
    lot = fetch_lot("lolpop")
    photo = (lot or {}).get("image")
    return [
        (None, SAMPLE_NOTE.format("1/3 daily summary: floors are real, the 24h changes are made up.")
         + daily_message(date, today, prev, names)),
        (photo, SAMPLE_NOTE.format("2/3 new collection with a picture.") + new_gift_message("lolpop", names, lot)),
        (None, SAMPLE_NOTE.format("3/3 new collection as text, used when the picture cannot be loaded.")
         + new_gift_message("lolpop", names, lot)),
    ]


def _call(token, method, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data,
                                 headers={"User-Agent": UA})
    with urlopen_retry(req) as r:
        if not json.load(r).get("ok"):
            raise RuntimeError("Telegram refused the message")


def send(token, chat_id, text):
    _call(token, "sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                 "disable_web_page_preview": "true"})


def send_photo(token, chat_id, photo_url, caption):
    """Photo with a caption; if Telegram cannot fetch or accept the picture, send the text alone."""
    if photo_url and len(caption) <= CAPTION_LIMIT:
        try:
            _call(token, "sendPhoto", {"chat_id": chat_id, "photo": photo_url, "caption": caption,
                                       "parse_mode": "HTML"})
            return
        except (urllib.error.URLError, RuntimeError):
            pass
    send(token, chat_id, caption)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print messages, send nothing, keep state")
    ap.add_argument("--test", action="store_true", help="send one test message to the channel and exit")
    args = ap.parse_args(argv)
    token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if args.test:
        if not (token and chat):
            print("error: set TG_BOT_TOKEN and TG_CHAT_ID", file=sys.stderr)
            return 1
        posts = sample_posts()
        for photo, text in posts:
            if photo:
                send_photo(token, chat, photo, text)
            else:
                send(token, chat, text)
        print(f"sent {len(posts)} sample posts")
        return 0
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": UA})
    with urlopen_retry(req) as r:
        days = parse_rows(r.read().decode("utf-8"))
    state = load_state()
    date, today, prev, new_slugs, new_state, post_daily = plan(days, state)
    if not post_daily:
        print("nothing to post")
        if not args.dry_run and new_state != state:
            save_state(new_state)
        return 0
    names = fetch_names()
    posts = [(None, daily_message(date, today, prev, names))]
    for slug in new_slugs:
        lot = fetch_lot(slug)
        posts.append(((lot or {}).get("image"), new_gift_message(slug, names, lot)))
    if args.dry_run:
        print("\n\n---\n\n".join(f"[photo: {p}]\n{t}" if p else t for p, t in posts))
        return 0
    if not (token and chat):
        print("error: set TG_BOT_TOKEN and TG_CHAT_ID", file=sys.stderr)
        return 1
    for photo, text in posts:
        if photo:
            send_photo(token, chat, photo, text)
        else:
            send(token, chat, text)
    save_state(new_state)
    print(f"posted {len(posts)} message(s) for {date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
