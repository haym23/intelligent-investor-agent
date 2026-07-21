# Quickstart: talking to Graham

## One-time setup

```bash
cd portfolio-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m portfolio.cli init
```

Get a free FMP key at financialmodelingprep.com (250 req/day). Then, **in the
same shell, before starting Pi**:

```bash
export FMP_API_KEY=your_key_here
export OPENROUTER_API_KEY=sk-or-...      # optional
pi
```

Order matters: activate the venv and export first, then launch Pi. Pi's bash
calls inherit the environment, but activating *inside* a Pi call won't persist.

## Session 1 — first candidates

Paste these in order.

**1. Orient**
> Read AGENTS.md and SYSTEM.md, list the skills in .pi/skills/, and confirm
> FMP_API_KEY is set by running `env | grep -c FMP_API_KEY`. Don't analyze
> anything yet.

**2. Generate ideas**
> Use the find-candidates skill. Propose 10 US-listed tickers that plausibly
> pass Graham's defensive criteria — mature, profitable, long dividend records,
> trading near or below book. One line each on why. Don't add them yet.

**3. Verify** (after you cut the list)
> Add the ones I kept to the watchlist, update their data, and rank them.
> Report using score_of_available, and for each one tell me which failures were
> real versus missing data.

**4. Go deep on survivors**
> Run the full analyze pipeline on the top 3. Give me margin of safety against
> the Graham number for each, and tell me plainly whether any of them qualify
> as investments rather than speculations.

**5. Look at it**
> Show me the dashboard.

## Prompts that get the most out of it

**Force it to the tools.** The highest-value habit:
> For any financial figure, run the command and quote the JSON. If a value is
> null, say it's unavailable rather than estimating.

**Ask for the failure reason, not the verdict.** "Why did VZ fail?" beats
"should I buy VZ?" every time.

**Make it argue against itself.**
> Make the strongest case against buying this, using only the numbers in the
> screen output.

**Use it as a discipline check.**
> I'm tempted to buy NVDA. Talk me through whether that's investment or
> speculation by your definition.

**Invoke skills by name** when you want determinism: `/skill:graham-screen`,
`/skill:find-candidates`.

## Ongoing

```
> Update all my positions and tell me if any verdict changed since last time.
> What's my portfolio worth and what's my P/L?
> Has anything in my watchlist dropped into buy range?
```

The `analysis_runs` table keeps every verdict timestamped, so "what changed"
is a real question with a real answer.

## Watch out for

- **Request budget.** Each ticker costs ~4 FMP calls; 250/day free. Don't add
  60 tickers at once.
- **5-year history.** Rules marked LIMITED passed on 5 years, not Graham's
  10/20. Weaker evidence — Pi is instructed to disclose this.
- **P/B <= 1.5 is brutal.** Most quality companies fail it today. If everything
  scores badly, that's the screen working as designed, not a bug. Tune the
  thresholds in `graham.py` if you want a modernized version.
