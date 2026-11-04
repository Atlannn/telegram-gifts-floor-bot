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
Telegram gifts floor prices, 5 Nov 2026

Highest floors (GRAM)
plushpepe: 7 500 (auction price, no fixed-price lot)
algorithmcup: 3 450
...
Up since yesterday
lolpop: 37 (was 30, +23%)
Down since yesterday
...
```

Moves are computed on **fixed-price floors** only (auction prices jump around), for gifts priced at 20 GRAM
or more, with a change of at least 10%, top 5 up and top 5 down. Constants are at the top of `bot.py`.
A gift that appears in the data for the first time gets its own "New gift collection" post.

## Run your own copy

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Create a channel and add the bot as an administrator with the right to post.
3. Fork this repo. In Settings, Secrets and variables, Actions, add `TG_BOT_TOKEN` and `TG_CHAT_ID`
   (the channel, e.g. `@my_channel`).
4. In the Actions tab run "Post to Telegram channel" once with *dry run* on, then let the schedule work
   (07:00 UTC daily). `state.json` remembers known collections and the last posted day.

Locally: `python bot.py --dry-run` prints the messages and sends nothing. Python 3.9+, standard library only.
Tokens are read from the environment and are never stored in the repo.

## Notes

- Prices are in GRAM (the coin formerly called TON). A floor is the cheapest lot, an asking price, not a
  sale price; fees are not included.
- A new collection is announced when the dataset first contains it, so up to a day after it appears on Fragment.
  A collection with nothing for sale has no row and is announced only once a lot is listed.
- Collection names are Fragment slugs (`plushpepe`), not display names.

## License

MIT. Data: CC BY 4.0, credit "Telegram gifts floor prices, Baltic Assets" with a link to https://balticassets.eu.
