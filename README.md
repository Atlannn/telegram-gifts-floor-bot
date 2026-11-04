# telegram-gifts-floor-bot: daily Telegram gift floor prices in a channel

A small script that posts to a Telegram channel once a day: the highest floors, the gifts whose floor
moved the most since yesterday, and a separate post for every **new gift collection** that appears on
[Fragment](https://fragment.com/gifts). It runs on GitHub Actions, so there is no server to host.

Data comes from the open dataset
[telegram-gifts-floor-price](https://github.com/Atlannn/telegram-gifts-floor-price)
(one CSV, updated daily). Live tool with rarity and a net-profit calculator:
[Telegram Gifts checker on Baltic Assets](https://balticassets.eu/en/crypto/telegram-gifts/).

## What a post looks like

```
Telegram Gifts · Floor Prices
5 Nov 2026

🏆 Highest floors
Plush Pepes: 7 500 GRAM (auction)
Algorithm Cups: 3 450 GRAM
...
📈 Up in 24h
Toy Bears: 37 (+25%)
📉 Down in 24h
Durov's Glasses: 150 (-15%)
```

The post is HTML-formatted with collection names linked to Fragment. A new collection comes with a picture
of its cheapest lot (taken from Fragment); if Telegram cannot load the picture the post is sent as text.

Moves are computed on **fixed-price floors** only (auction prices jump around), for gifts priced at 20 GRAM
or more, with a change of at least 10%, top 5 up and top 5 down. Constants are at the top of `bot.py`.
A gift that appears in the data for the first time gets its own "New gift collection" post.

New collections are caught faster by `check_new.py`: every 15 minutes it reads the list on
fragment.com/gifts (one request) and announces anything unseen. GitHub may delay scheduled runs by
10-30 minutes, so expect a post within roughly 15-45 minutes. The daily job and this check share
`state.json`, so a collection is announced only once.

## Run your own copy

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Create a channel and add the bot as an administrator with the right to post.
3. Fork this repo. In Settings, Secrets and variables, Actions, add `TG_BOT_TOKEN` and `TG_CHAT_ID`
   (the channel, e.g. `@my_channel`).
4. In the Actions tab run "Post to Telegram channel" and "Check for new gift collections" once each with
   *dry run* on, then let the schedules work (07:00 UTC daily, every 15 minutes). `state.json` remembers known collections and the last posted day.

Locally: `python bot.py --dry-run` prints the messages and sends nothing. Python 3.9+, standard library only.
Tokens are read from the environment and are never stored in the repo.

## Notes

- Prices are in GRAM (the coin formerly called TON). A floor is the cheapest lot, an asking price, not a
  sale price; fees are not included.
- A new collection is announced when it first shows up in the list on fragment.com/gifts (within about 15-45
  minutes). A suspicious list (under 50 collections, or more than 5 new at once) is ignored and reported as
  a warning instead of being posted.
- Collection names are Fragment slugs (`plushpepe`), not display names.

## License

MIT. Data: CC BY 4.0, credit "Telegram gifts floor prices, Baltic Assets" with a link to https://balticassets.eu.
