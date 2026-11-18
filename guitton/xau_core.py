"""GUITTON core: the trader-* method adapted to gold (data, sessions, replays).

The 11 trader skills are built for US stocks on NYSE hours. Gold trades almost
24 hours a day in lots of 100 oz, both ways, with leverage, so this module
re-implements the same chain for XAUUSD:

  clock -> daily context (scanner) -> news -> opening-range entry -> exit plan
  -> time machine (10,000 replays + history) -> lot sizing -> risk check
  -> ticket (never sent) -> alert levels

Data: Yahoo's free chart of GC=F, the COMEX gold future, as a proxy for spot
XAUUSD (Yahoo has no spot gold). The future trades a few dollars above spot;
give your broker's XAUUSD price and every level is shifted by the gap.
Standard library only.
"""
import json
import math
import random
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
PARIS = ZoneInfo("Europe/Paris")
SOURCE = "GC=F"
OZ_PER_LOT = 100
UA = "Mozilla/5.0 (compatible; trading-desk/1.0)"
CHART = "https://%s.finance.yahoo.com/v8/finance/chart/GC=F?range=%s&interval=%s"
RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US"

SESSIONS = {
    # name: (tz, opens, last entry, flat by)  -- the range is the first N minutes
    "london": ("Europe/London", "08:00", "12:00", "16:30", "Londres"),
    "ny": ("America/New_York", "08:20", "12:00", "16:30", "New York (COMEX)"),
}


# ------------------------------------------------------------------ data

def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def chart(rng, interval):
    last = None
    for host in ("query2", "query1"):
        try:
            d = json.loads(_get(CHART % (host, rng, interval)))
            res = d["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            bars = []
            for i, t in enumerate(res["timestamp"]):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                if None in (o, h, l, c):
                    continue
                bars.append((t, o, h, l, c))
            return bars, res["meta"]
        except Exception as e:  # noqa: BLE001 - try the other host
            last = e
            time.sleep(1)
    raise RuntimeError("Yahoo GC=F indisponible : %s" % last)


def headlines(hours=48, now=None):
    now = now or datetime.now(UTC)
    out = []
    try:
        root = ElementTree.fromstring(_get(RSS))
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        try:
            ts = datetime.strptime(it.findtext("pubDate") or "", "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            continue
        if now - ts > timedelta(hours=hours):
            continue
        low = title.lower()
        tags = sorted({tag for tag, words in (
            ("fed / taux", ("fed", "rate", "powell", "fomc", "yield")),
            ("inflation", ("cpi", "inflation", "pce", "ppi")),
            ("emploi", ("payroll", "jobs", "nfp", "unemployment")),
            ("dollar", ("dollar", "dxy")),
            ("géopolitique", ("war", "tariff", "sanction", "conflict", "iran", "russia", "china")),
        ) if any(w in low for w in words)})
        if not any(w in low for w in ("gold", "bullion", "xau", "precious", "fed", "inflation",
                                       "dollar", "cpi", "silver", "metal")):
            continue
        out.append({"title": title, "time": ts.astimezone(UTC).isoformat(), "link": it.findtext("link"),
                    "tags": tags})
    out.sort(key=lambda x: x["time"], reverse=True)
    return out, None


# ------------------------------------------------------------------ helpers

def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def futures_open(now_utc):
    """CME Globex gold: Sun 18:00 to Fri 17:00 New York, daily break 17:00-18:00."""
    n = now_utc.astimezone(NY)
    wd, mins = n.weekday(), n.hour * 60 + n.minute
    if wd == 5:
        return False, "samedi : marché fermé (réouverture dimanche 18h00 New York)"
    if wd == 6 and mins < 18 * 60:
        return False, "dimanche : réouverture à 18h00 New York"
    if wd == 4 and mins >= 17 * 60:
        return False, "vendredi soir : marché fermé jusqu'à dimanche 18h00 New York"
    if 17 * 60 <= mins < 18 * 60:
        return False, "pause quotidienne 17h00-18h00 New York"
    return True, "marché de l'or ouvert"


def rsi14(closes):
    if len(closes) < 16:
        return None
    gains = [max(0, closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    losses = [max(0, closes[i - 1] - closes[i]) for i in range(1, len(closes))]
    ag, al = sum(gains[:14]) / 14, sum(losses[:14]) / 14
    for g, l in zip(gains[14:], losses[14:]):
        ag, al = (ag * 13 + g) / 14, (al * 13 + l) / 14
    return 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 1)


def daily_context(daily):
    closes = [b[4] for b in daily]
    out = {"close": round(closes[-1], 2), "prev_close": round(closes[-2], 2),
           "change_pct": round((closes[-1] / closes[-2] - 1) * 100, 2), "rsi": rsi14(closes), "setups": []}
    trs = [max(b[2], daily[i - 1][4]) - min(b[3], daily[i - 1][4]) for i, b in enumerate(daily) if i]
    out["atr_daily"] = round(sum(trs[-14:]) / 14, 2)
    ma = lambda n, k=0: sum(closes[-n - k:len(closes) - k]) / n
    out["ma20"], out["ma50"] = round(ma(20), 2), round(ma(50), 2)
    out["trend"] = ("haussière" if closes[-1] > out["ma20"] > out["ma50"] else
                    "baissière" if closes[-1] < out["ma20"] < out["ma50"] else "neutre")
    if closes[-1] > max(closes[-21:-1]):
        out["setups"].append("plus haute clôture 20 j")
    if closes[-1] < min(closes[-21:-1]):
        out["setups"].append("plus basse clôture 20 j")
    if closes[-2] < ma(20, 1) and closes[-1] > ma(20):
        out["setups"].append("repasse au-dessus de la moyenne 20 j")
    if closes[-2] > ma(20, 1) and closes[-1] < ma(20):
        out["setups"].append("repasse sous la moyenne 20 j")
    r = out["rsi"]
    if r is not None and r < 30:
        out["setups"].append("survendu (RSI<30)")
    if r is not None and r > 70:
        out["setups"].append("suracheté (RSI>70)")
    return out


# ------------------------------------------------------------------ sessions

def sessions(bars, sess, or_minutes):
    """{date: [(start_utc_ts, minute_of_day, o, h, l, c)]} restricted to open..flat."""
    tzname, opens, _, flat, _ = SESSIONS[sess]
    tz = ZoneInfo(tzname)
    lo, hi = hm(opens), hm(flat)
    out = {}
    for t, o, h, l, c in bars:
        if t % 300:
            continue  # the live tick, not a 5-minute bar
        d = datetime.fromtimestamp(t, UTC).astimezone(tz)
        m = d.hour * 60 + d.minute
        if lo <= m < hi:
            out.setdefault(d.date().isoformat(), []).append((t, m, o, h, l, c))
    return out


def opening_range(day_bars, sess, or_minutes):
    lo = hm(SESSIONS[sess][1])
    rb = [b for b in day_bars if lo <= b[1] < lo + or_minutes]
    if len(rb) != or_minutes // 5:
        return None
    return {"high": round(max(b[3] for b in rb), 2), "low": round(min(b[4] for b in rb), 2)}


def find_trigger(day_bars, rng, sess, or_minutes, upto_min, allow_short):
    """First completed bar after the range closing outside it, before upto_min."""
    opens, last_entry = hm(SESSIONS[sess][1]), hm(SESSIONS[sess][2])
    for i, b in enumerate(day_bars):
        if b[1] < opens + or_minutes or b[1] + 5 > min(upto_min, last_entry):
            continue
        if b[5] > rng["high"]:
            return {"side": "buy", "price": round(b[5], 2), "index": i, "minute": b[1] + 5}
        if allow_short and b[5] < rng["low"]:
            return {"side": "sell", "price": round(b[5], 2), "index": i, "minute": b[1] + 5}
    return None


def make_levels(side, entry, rng, stop_rule, target_r, atr5):
    sgn = 1 if side == "buy" else -1
    if stop_rule == "or-mid":
        stop = (rng["high"] + rng["low"]) / 2
    elif stop_rule == "or-opp":
        stop = rng["low"] if side == "buy" else rng["high"]
    elif stop_rule.startswith("pct:"):
        stop = entry * (1 - sgn * float(stop_rule[4:]) / 100)
    elif stop_rule.startswith("atr:"):
        stop = entry - sgn * float(stop_rule[4:]) * atr5
    else:
        raise ValueError(stop_rule)
    stop = round(stop, 2)
    risk = round((entry - stop) * sgn, 2)
    if risk <= 0:
        return None
    return {"side": side, "entry": round(entry, 2), "stop": stop,
            "target": round(entry + sgn * target_r * risk, 2), "risk": risk}


def walk(bars, lv):
    """Outcome of a plan over real bars: 'target', 'stop' or 'close' and R."""
    sgn = 1 if lv["side"] == "buy" else -1
    last = lv["entry"]
    for b in bars:
        h, l, c = b[3], b[4], b[5]
        if (l <= lv["stop"]) if sgn > 0 else (h >= lv["stop"]):
            return "stop", -1.0
        if (h >= lv["target"]) if sgn > 0 else (l <= lv["target"]):
            return "target", round((lv["target"] - lv["entry"]) * sgn / lv["risk"], 2)
        last = c
    return "close", round((last - lv["entry"]) * sgn / lv["risk"], 2)


def atr5(day_bars, upto_index, prev_bars):
    seq = (prev_bars + day_bars[:upto_index + 1])[-15:]
    trs = [max(b[3], seq[i - 1][5]) - min(b[4], seq[i - 1][5]) for i, b in enumerate(seq) if i]
    return sum(trs) / len(trs) if trs else 0


# ------------------------------------------------------------------ time machine

def time_machine(days, today, lv, start_minute, sess, replays=10000, seed=19, window=2):
    """Replay the rest of the session from past bars at the same time of day."""
    flat = hm(SESSIONS[sess][3])
    pool = {}
    for d, bs in days.items():
        if d >= today:
            continue
        for i in range(1, len(bs)):
            prev, b = bs[i - 1][5], bs[i]
            pool.setdefault(b[1], []).append((b[3] / prev, b[4] / prev, b[5] / prev))
    slots = list(range(start_minute, flat, 5))
    pools = []
    for m in slots:
        p = []
        for k in range(-window, window + 1):
            p += pool.get(m + 5 * k, [])
        pools.append(p)
    if not slots or any(not p for p in pools):
        return None
    rnd = random.Random(seed)
    sgn = 1 if lv["side"] == "buy" else -1
    hit_t = hit_s = 0
    rs, finals = [], []
    for _ in range(replays):
        px, res = lv["entry"], None
        for p in pools:
            hr, lr, cr = p[rnd.randrange(len(p))]
            h, l = px * hr, px * lr
            if (l <= lv["stop"]) if sgn > 0 else (h >= lv["stop"]):
                res = -1.0
                hit_s += 1
                break
            if (h >= lv["target"]) if sgn > 0 else (l <= lv["target"]):
                res = (lv["target"] - lv["entry"]) * sgn / lv["risk"]
                hit_t += 1
                break
            px *= cr
        if res is None:
            res = (px - lv["entry"]) * sgn / lv["risk"]
        rs.append(res)
        finals.append(px)
    finals.sort()
    n = float(replays)
    return {"replays": replays, "seed": seed, "bars": len(slots),
            "p_target": round(hit_t / n, 4), "p_stop": round(hit_s / n, 4),
            "p_neither": round(1 - (hit_t + hit_s) / n, 4),
            "avg_R": round(sum(rs) / n, 3),
            "p5": round(finals[int(n * .05)], 2), "median": round(finals[int(n * .5)], 2),
            "p95": round(finals[int(n * .95)], 2)}


def history(days, today, sess, or_minutes, stop_rule, target_r, allow_short):
    trades = []
    dates = sorted(d for d in days if d < today)
    for j, d in enumerate(dates):
        bs = days[d]
        rng = opening_range(bs, sess, or_minutes)
        if not rng or rng["high"] == rng["low"]:
            continue
        trig = find_trigger(bs, rng, sess, or_minutes, 24 * 60, allow_short)
        if not trig:
            continue
        prev = days[dates[j - 1]] if j else []
        lv = make_levels(trig["side"], trig["price"], rng, stop_rule, target_r,
                         atr5(bs, trig["index"], prev))
        if not lv:
            continue
        out, r = walk(bs[trig["index"] + 1:], lv)
        trades.append({"date": d, "side": trig["side"], "entry": lv["entry"], "outcome": out, "R": r})
    n = len(trades)
    return {"sessions": len(dates), "triggered": n,
            "target": sum(t["outcome"] == "target" for t in trades),
            "stop": sum(t["outcome"] == "stop" for t in trades),
            "close": sum(t["outcome"] == "close" for t in trades),
            "avg_R": round(sum(t["R"] for t in trades) / n, 3) if n else None,
            "trades": trades[-15:]}
