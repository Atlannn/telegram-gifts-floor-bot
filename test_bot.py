import bot

D1 = {"a": {"floor": 100.0, "fixed": 100.0}, "b": {"floor": 5.0, "fixed": 5.0}, "c": {"floor": 50.0, "fixed": 50.0},
      "pepe": {"floor": 7000.0, "fixed": None}}
D2 = {"a": {"floor": 120.0, "fixed": 120.0}, "b": {"floor": 9.0, "fixed": 9.0}, "c": {"floor": 40.0, "fixed": 40.0},
      "pepe": {"floor": 7500.0, "fixed": None}, "new1": {"floor": 30.0, "fixed": 30.0}}
DAYS = {"2026-11-04": D1, "2026-11-05": D2}


def test_movers_threshold_and_min_price():
    up, down = bot.movers(D2, D1)
    assert [m[0] for m in up] == ["a"]       # +20%; b is +80% but under MIN_PRICE
    assert [m[0] for m in down] == ["c"]     # -20%
    assert bot.movers(D2, {}) == ([], [])


def test_pepe_without_fixed_is_not_a_mover():
    assert "pepe" not in [m[0] for m in sum(bot.movers(D2, D1), [])]


def test_first_run_seeds_state_and_posts_nothing():
    msgs, st = bot.plan(DAYS, {"known": [], "last_posted": None})
    assert msgs == [] and st["last_posted"] == "2026-11-05" and "new1" in st["known"]


def test_daily_post_and_new_gift():
    msgs, st = bot.plan(DAYS, {"known": ["a", "b", "c", "pepe"], "last_posted": "2026-11-04"})
    assert len(msgs) == 2
    assert "5 Nov 2026" in msgs[0] and "auction price" in msgs[0] and "+20%" in msgs[0]
    assert "new1" in msgs[1] and "New gift collection" in msgs[1]
    assert "new1" in st["known"]


def test_same_day_is_not_posted_twice():
    state = {"known": ["a"], "last_posted": "2026-11-05"}
    assert bot.plan(DAYS, state) == ([], state)


def test_parse_rows():
    text = "date,collection,floor_gram,floor_fixed_gram,lots_seen,auctions_seen\n2026-11-04,x,5.0,,3,3\n"
    assert bot.parse_rows(text) == {"2026-11-04": {"x": {"floor": 5.0, "fixed": None}}}
