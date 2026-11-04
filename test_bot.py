import bot

D1 = {"a": {"floor": 100.0, "fixed": 100.0}, "b": {"floor": 5.0, "fixed": 5.0}, "c": {"floor": 50.0, "fixed": 50.0},
      "pepe": {"floor": 7000.0, "fixed": None}}
D2 = {"a": {"floor": 120.0, "fixed": 120.0}, "b": {"floor": 9.0, "fixed": 9.0}, "c": {"floor": 40.0, "fixed": 40.0},
      "pepe": {"floor": 7500.0, "fixed": None}, "new1": {"floor": 30.0, "fixed": 30.0}}
DAYS = {"2026-11-04": D1, "2026-11-05": D2}
NAMES = {"a": "Alpha Caps", "pepe": "Plush Pepes"}

LIST_PAGE = ('<a href="/gifts/durovscap" class="tm-main-filters-item" data-value="durovscap"> '
             '<div class="tm-main-filters-photo"><img src="/file/x.webp" /></div> '
             '<div class="tm-main-filters-name">Durov&#39;s Caps</div> '
             '<div class="tm-main-filters-count">3,270</div> </a>')
LOT_PAGE = ('<a href="/gift/lolpop-98734" class="tm-grid-item"><div class="tm-grid-item-thumb">'
            '<img src="https://nft.fragment.com/gift/lolpop-98734.medium.jpg" class="tm-grid-thumb"/></div>'
            '<span class="item-name">Lol Pop</span><div class="js-timer-wrap"></div>'
            '<div class="tm-grid-item-value tm-value icon-before icon-ton">5</div></a>')


def test_movers_threshold_and_min_price():
    up, down = bot.movers(D2, D1)
    assert [m[0] for m in up] == ["a"]       # +20%; b is +80% but under MIN_PRICE
    assert [m[0] for m in down] == ["c"]     # -20%
    assert bot.movers(D2, {}) == ([], [])


def test_pepe_without_fixed_is_not_a_mover():
    assert "pepe" not in [m[0] for m in sum(bot.movers(D2, D1), [])]


def test_first_run_seeds_state_and_posts_nothing():
    _, _, _, new, st, post = bot.plan(DAYS, {"known": [], "last_posted": None})
    assert not post and new == [] and st["last_posted"] == "2026-11-05" and "new1" in st["known"]


def test_daily_plan_finds_new_gift():
    _, _, _, new, st, post = bot.plan(DAYS, {"known": ["a", "b", "c", "pepe"], "last_posted": "2026-11-04"})
    assert post and new == ["new1"] and "new1" in st["known"]


def test_same_day_is_not_posted_twice():
    state = {"known": ["a"], "last_posted": "2026-11-05"}
    assert bot.plan(DAYS, state)[4:] == (state, False)


def test_daily_message_format():
    text = bot.daily_message("2026-11-05", D2, D1, NAMES)
    assert "5 Nov 2026" in text and "Plush Pepes</a>: <b>7 500 GRAM</b> (auction)" in text
    assert "Alpha Caps" in text and "+20%" in text and "Up in 24h" in text and "Down in 24h" in text


def test_daily_message_without_names_falls_back_to_slug():
    assert ">pepe</a>" in bot.daily_message("2026-11-05", D2, D1)


def test_parse_names_and_lot():
    assert bot.parse_names(LIST_PAGE) == {"durovscap": "Durov's Caps"}
    lot = bot.parse_cheapest_lot(LOT_PAGE)
    assert lot == {"name": "Lol Pop", "image": "https://nft.fragment.com/gift/lolpop-98734.medium.jpg",
                   "price": 5.0, "auction": True}
    assert bot.parse_cheapest_lot("<html></html>") is None


def test_new_gift_message_with_and_without_lot():
    lot = bot.parse_cheapest_lot(LOT_PAGE)
    text = bot.new_gift_message("lolpop", {}, lot)
    assert "New gift collection: Lol Pop" in text and "Floor: <b>5 GRAM</b> (auction)" in text
    assert "fragment.com/gifts/lolpop" in text
    assert "New gift collection: lolpop" in bot.new_gift_message("lolpop")


def test_parse_rows():
    text = "date,collection,floor_gram,floor_fixed_gram,lots_seen,auctions_seen\n2026-11-04,x,5.0,,3,3\n"
    assert bot.parse_rows(text) == {"2026-11-04": {"x": {"floor": 5.0, "fixed": None}}}


def test_photo_falls_back_to_text(monkeypatch):
    calls = []

    def fake_call(token, method, fields):
        calls.append(method)
        if method == "sendPhoto":
            raise RuntimeError("bad photo")
    monkeypatch.setattr(bot, "_call", fake_call)
    bot.send_photo("t", "@c", "https://x/y.jpg", "caption")
    assert calls == ["sendPhoto", "sendMessage"]


def test_sample_posts_cover_every_kind(monkeypatch):
    csv_text = ("date,collection,floor_gram,floor_fixed_gram,lots_seen,auctions_seen\n"
                "2026-11-04,a,100.0,100.0,3,0\n2026-11-04,b,200.0,200.0,3,0\n2026-11-04,pepe,7000.0,,3,3\n")

    class Resp:
        def read(self):
            return csv_text.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(bot.urllib.request, "urlopen", lambda *a, **k: Resp())
    monkeypatch.setattr(bot, "fetch_names", lambda: {})
    monkeypatch.setattr(bot, "fetch_lot", lambda slug: bot.parse_cheapest_lot(LOT_PAGE))
    posts = bot.sample_posts()
    assert len(posts) == 3
    assert posts[0][0] is None and "Up in 24h" in posts[0][1] and "Down in 24h" in posts[0][1]
    assert posts[1][0].endswith(".jpg") and posts[2][0] is None
    assert all("SAMPLE POST" in t for _, t in posts)
