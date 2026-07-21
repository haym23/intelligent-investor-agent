---
name: find-candidates
description: Generate and evaluate new stock candidates for Graham-style value investing. Use when the user asks what they should buy, wants ideas, asks for candidates or screening prospects, or has nothing in their watchlist yet. This combines your own knowledge of which companies structurally fit Graham's criteria with the deterministic screen to verify them.
---

# Find Candidates

There is no market-wide screener in this tool. Candidate *generation* is your
job; candidate *verification* is the CLI's job. Never skip the verification.

## Step 1 — Propose, don't add

Suggest 8–12 US-listed tickers that plausibly meet defensive-investor criteria.
Reason from structural characteristics:

- **Favor**: mature industrials, utilities, telecoms, insurers, banks,
  automakers, consumer staples, integrated energy. Companies with long dividend
  records, tangible book value, and unexciting growth.
- **Avoid**: anything trading far above book (most software/tech), recent IPOs,
  companies without positive earnings across the cycle, biotech, speculative
  growth. These fail P/B <= 1.5 almost by definition.
- Prefer companies whose price has been unremarkable lately. Graham hunted
  neglect, not momentum.

Present the list with one line each on *why it might fit* — then STOP and let
the user cut it. Do not add tickers unprompted.

## Step 2 — Add and fetch

```bash
python -m portfolio.cli watch TICKER1 TICKER2 TICKER3
python -m portfolio.cli update --all
```

`watch` adds with zero shares so nothing distorts the user's P/L. `update`
pulls prices and fundamentals (FMP if `FMP_API_KEY` is set, else yfinance).

Note the FMP free tier is ~250 requests/day and each ticker costs ~4. Don't add
sixty tickers at once.

## Step 3 — Rank

```bash
python -m portfolio.cli rank --json
```

Returns every screened ticker sorted by score, with `score_of_available`,
`real_failures`, `missing_data_rules`, `limited_history_rules`, and
`margin_of_safety`.

## Step 4 — Report like Graham

Rank by *testable* rules passed, not raw score. For each serious candidate give:
the score in honest form, which rules genuinely failed and by how much, the
margin of safety against the Graham number, and your judgment on whether it
merits deeper work.

Dismiss the clear failures briefly — don't spend paragraphs on a company
trading at 15x book. Concentrate on the two or three worth real attention, and
say plainly if none of them qualify. Recommending nothing is a legitimate
outcome; cash is a position.

Then suggest `analyze` on the survivors for a full verdict with news.
