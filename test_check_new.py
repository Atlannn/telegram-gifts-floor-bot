import check_new

SLUGS = [f"g{i}" for i in range(60)]
STATE = {"known": SLUGS, "last_posted": "2026-11-04"}


def test_parse_slugs():
    page = '<a href="/gifts/plushpepe">x</a><a href="/gifts/lolpop?x=1">y</a><a href="/gifts/plushpepe">z</a>'
    assert check_new.parse_slugs(page) == ["lolpop", "plushpepe"]


def test_announces_one_new_collection_once():
    new, st, err = check_new.plan(SLUGS + ["fresh"], STATE)
    assert err is None and new == ["fresh"] and "fresh" in st["known"]
    assert st["last_posted"] == "2026-11-04"
    new2, st2, _ = check_new.plan(SLUGS + ["fresh"], st)
    assert new2 == [] and st2 == st


def test_nothing_new():
    assert check_new.plan(SLUGS, STATE) == ([], STATE, None)


def test_short_list_is_ignored():
    new, st, err = check_new.plan(["a", "b"], STATE)
    assert new == [] and st == STATE and err


def test_many_new_at_once_is_ignored():
    new, st, err = check_new.plan(SLUGS + [f"n{i}" for i in range(6)], STATE)
    assert new == [] and st == STATE and err


def test_first_run_only_remembers():
    new, st, err = check_new.plan(SLUGS, {"known": [], "last_posted": None})
    assert new == [] and st["known"] == SLUGS and err is None
