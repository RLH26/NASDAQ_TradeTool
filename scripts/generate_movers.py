import csv, json, re
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

# --- Settings you can tweak ---
LOOKBACK_DAYS = 8              # fetch enough calendar days to cover ~5 trading days
TRADING_LOOKBACK = 6           # approx last 6 closes used to compute 5D
ONE_DAY_JUMP_PCT = 0.20        # >20% in a day
FIVE_DAY_MOVE_PCT = 0.20       # or >20% over last ~5 days
NEWS_LOOKBACK_HOURS = 48       # "prior to the jump" window
NEWS_HIT_THRESHOLD = 2         # <= this => "no_obvious_news" (tune)

# NASDAQ list
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"

# Prices: Stooq daily CSV
STOOQ_URL = "https://stooq.com/q/d/l/?s={sym}&i=d"

# News: GDELT Doc 2.0 API (JSON)
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

UA = "NASDAQTradeTool/1.0 (personal research)"

def get(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def nasdaq_tickers():
    txt = get(NASDAQ_LISTED_URL)
    lines = [l for l in txt.splitlines() if l and not l.startswith("File Created")]
    reader = csv.DictReader(lines, delimiter="|")
    tickers = []
    for row in reader:
        sym = (row.get("Symbol") or "").strip()
        if not sym or sym == "Symbol": 
            continue
        if (row.get("Test Issue","N").strip() == "Y"):
            continue
        # keep ETFs too; you can filter later if you want
        tickers.append(sym)
    return tickers

def stooq_symbol(ticker: str) -> str:
    # stooq commonly uses lowercase and "-" for dots
    return ticker.lower().replace(".", "-")

def fetch_closes(ticker: str):
    url = STOOQ_URL.format(sym=stooq_symbol(ticker))
    csv_txt = get(url)
    if "Date,Open,High,Low,Close,Volume" not in csv_txt:
        return []
    rows = list(csv.DictReader(csv_txt.splitlines()))
    out = []
    for r in rows[-80:]:  # last ~80 rows available quickly
        try:
            out.append((r["Date"], float(r["Close"])))
        except:
            pass
    return out

def pct_change(a, b):
    if a is None or b is None or a == 0:
        return None
    return (b / a) - 1.0

def gdelt_query(ticker: str, start_utc: datetime, end_utc: datetime):
    # GDELT query: match ticker as a keyword plus company-ish context is hard.
    # For MVP, use ticker keyword and restrict to English.
    start = start_utc.strftime("%Y%m%d%H%M%S")
    end = end_utc.strftime("%Y%m%d%H%M%S")

    # search " TICKER " or "$TICKER" patterns broadly
    q = f'("{ticker}" OR "${ticker}") lang:english'
    params = f"?query={quote(q)}&mode=artlist&format=json&maxrecords=25&startdatetime={start}&enddatetime={end}&sort=hybridrel"
    url = GDELT_DOC_URL + params
    try:
        data = json.loads(get(url))
        arts = data.get("articles", []) or []
    except:
        arts = []

    headlines = []
    for a in arts[:10]:
        headlines.append({
            "title": a.get("title",""),
            "url": a.get("url",""),
            "published": a.get("seendate","") or a.get("datetime","") or ""
        })
    return len(arts), headlines

def quote(s: str) -> str:
    # minimal URL encoding
    from urllib.parse import quote as q
    return q(s, safe="")

def main():
    tickers = nasdaq_tickers()

    items = []
    checked = 0

    for t in tickers:
        checked += 1
        closes = fetch_closes(t)
        if len(closes) < TRADING_LOOKBACK:
            continue

        # use last ~6 closes for 5D window
        window = closes[-TRADING_LOOKBACK:]
        dates = [d for d,_ in window]
        px = [p for _,p in window]

        # 1D jump: max over window
        best = None
        for i in range(1, len(px)):
            ch = pct_change(px[i-1], px[i])
            if ch is None: 
                continue
            if best is None or ch > best["one_day_jump"]:
                best = {"jump_date": dates[i], "one_day_jump": ch, "prev": px[i-1], "close": px[i]}

        if not best:
            continue

        five_day = pct_change(px[0], px[-1]) or 0.0

        if best["one_day_jump"] < ONE_DAY_JUMP_PCT and five_day < FIVE_DAY_MOVE_PCT:
            continue

        # News window: 48h prior to jump_date (approx: treat jump date at 20:00 UTC)
        jump_dt = datetime.fromisoformat(best["jump_date"]).replace(tzinfo=timezone.utc) + timedelta(hours=20)
        start = jump_dt - timedelta(hours=NEWS_LOOKBACK_HOURS)
        end = jump_dt

        hits, headlines = gdelt_query(t, start, end)

        classification = "no_obvious_news" if hits <= NEWS_HIT_THRESHOLD else "headlines_found"

        items.append({
            "ticker": t,
            "jump_date": best["jump_date"],
            "one_day_jump": best["one_day_jump"],
            "five_day_move": five_day,
            "news_hits": hits,
            "news_classification": classification,
            "top_headlines": headlines
        })

        # keep runtime sane
        if len(items) >= 350:
            break

    items.sort(key=lambda x: (x["one_day_jump"], x["five_day_move"], -x["news_hits"]), reverse=True)

    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "lookback_days": 5,
        "thresholds": {
            "one_day_jump_pct": int(ONE_DAY_JUMP_PCT * 100),
            "five_day_move_pct": int(FIVE_DAY_MOVE_PCT * 100),
            "news_window_hours": NEWS_LOOKBACK_HOURS,
            "no_news_if_hits_leq": NEWS_HIT_THRESHOLD
        },
        "items": items
    }

    import os
    os.makedirs("docs", exist_ok=True)
    with open("docs/movers.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

if __name__ == "__main__":
    main()
