"""XAUUSD desk: the trader-* method adapted to gold.

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


# ------------------------------------------------------------------ sizing / risk

def size(lv, s, spread):
    cap = float(s["capital"])
    risk_usd = cap * float(s["risk_pct"]) / 100
    lev = float(s.get("xau_leverage") or 20)
    per_oz = lv["risk"] + spread
    lots = math.floor(risk_usd / (per_oz * OZ_PER_LOT) * 100 + 1e-9) / 100
    out = {"risk_budget": round(risk_usd, 2), "risk_per_oz": round(per_oz, 2)}
    if lots < 0.01:
        out["refusal"] = ("Stop trop large : 0,01 lot risquerait %.2f $ pour un budget de %.2f $"
                          % (per_oz * 1, risk_usd))
        return out
    # margin cap: never more than 50 % of the capital tied up
    max_lots_margin = math.floor(cap * 0.5 * lev / (lv["entry"] * OZ_PER_LOT) * 100) / 100
    bound = "perte max"
    if max_lots_margin < lots:
        lots, bound = max_lots_margin, "marge (50 % du capital)"
    if lots < 0.01:
        out["refusal"] = "Marge insuffisante pour 0,01 lot au levier 1:%d" % lev
        return out
    notional = lots * OZ_PER_LOT * lv["entry"]
    out.update(lots=round(lots, 2), oz=round(lots * OZ_PER_LOT, 2), notional=round(notional, 2),
               margin=round(notional / lev, 2), leverage_used=round(notional / cap, 2),
               max_loss=round(lots * OZ_PER_LOT * per_oz, 2),
               gain_at_target=round(lots * OZ_PER_LOT * (abs(lv["target"] - lv["entry"]) - spread), 2),
               bound_by=bound, broker_leverage=lev)
    return out


def risk_check(lv, sz, s, live, now_min, sess, market_ok):
    reasons, info = [], []
    if sz.get("refusal"):
        reasons.append(sz["refusal"])
        return "BLOCK", reasons, info
    rr = (abs(lv["target"] - lv["entry"])) / lv["risk"]
    if rr < 1:
        reasons.append("reward:risk %.2f sous le minimum 1" % rr)
    if sz["max_loss"] > sz["risk_budget"] + 0.01:
        reasons.append("perte max %.2f $ au-dessus du budget %.2f $" % (sz["max_loss"], sz["risk_budget"]))
    if sz["margin"] > float(s["capital"]) * 0.5 + 0.01:
        reasons.append("marge au-dessus de 50 % du capital")
    if live:
        if not market_ok:
            reasons.append("marché fermé")
        if now_min > hm(SESSIONS[sess][2]):
            reasons.append("fenêtre d'entrée dépassée (%s)" % SESSIONS[sess][2])
    info.append("perte max %.2f $ (budget %.2f $), R:R %.2f, marge %.2f $"
                % (sz["max_loss"], sz["risk_budget"], rr, sz["margin"]))
    return ("BLOCK" if reasons else "PASS"), reasons, info


# ------------------------------------------------------------------ the chain

def step(skill, title, status, summary, data=None, text=""):
    return {"skill": skill, "title": title, "status": status, "summary": summary,
            "data": data, "text": text}


def analyze(s, now_utc=None):
    now_utc = now_utc or datetime.now(UTC)
    sess = s.get("xau_session") or "london"
    tzname, opens, last_entry, flat, label = SESSIONS[sess]
    tz = ZoneInfo(tzname)
    or_minutes = 15
    stop_rule = s.get("xau_stop") or "or-mid"
    target_r = float(str(s.get("target") or "2R").rstrip("R"))
    allow_short = bool(s.get("xau_allow_short", True))
    spread = float(s.get("xau_spread") or 0.35)
    steps, trade = [], {"symbol": "XAUUSD", "kind": "xau", "session": label}

    # 1. clock
    market_ok, why = futures_open(now_utc)
    local = now_utc.astimezone(tz)
    now_min = local.hour * 60 + local.minute

    # data
    try:
        bars, meta = chart("60d", "5m")
        daily, _ = chart("6mo", "1d")
    except RuntimeError as e:
        return {"symbol": "XAUUSD", "error": str(e), "steps": [], "trade": None}
    days = sessions(bars, sess, or_minutes)
    last_px = round(meta.get("regularMarketPrice") or bars[-1][4], 2)
    broker_px = s.get("xau_broker_price")
    offset = round(float(broker_px) - last_px, 2) if broker_px not in (None, "", 0, "0") else 0.0
    trade.update(source_price=last_px, offset=offset)

    today = local.date().isoformat()
    live = (market_ok and today in days and now_min >= hm(opens) + or_minutes + 5
            and now_min < hm(flat) and opening_range(days[today], sess, or_minutes) is not None)
    if live:
        day, upto = today, now_min
        mode = "live"
    else:
        complete = [d for d in sorted(days) if d < today or (d == today and now_min >= hm(flat))]
        complete = [d for d in complete if opening_range(days[d], sess, or_minutes)]
        if not complete:
            return {"symbol": "XAUUSD", "error": "Pas assez de données GC=F", "steps": [], "trade": None}
        day = complete[-1]
        upto = hm(opens) + or_minutes + 30
        mode = "rehearsal"
    trade.update(mode=mode, as_of="%s %s" % (day, "%02d:%02d" % divmod(upto, 60)))
    steps.append(step("trader-alerts", "Horloge (or, CME Globex)", "ok" if market_ok else "warn",
                      "%s · %s %s heure locale. %s" % (
                          why.capitalize(), label, local.strftime("%H:%M"),
                          "Analyse en direct." if live else
                          "Répétition sur la séance de %s du %s à %02d:%02d (range + 30 min)."
                          % (label, day, *divmod(upto, 60)))))

    # 2. daily context
    ctx = daily_context(daily)
    trade["context"] = ctx
    steps.append(step("trader-scanner", "Contexte journalier", "ok",
                      "Clôture %s (%+.2f %%), tendance %s, RSI %s, ATR jour %s $%s" % (
                          ctx["close"], ctx["change_pct"], ctx["trend"], ctx["rsi"], ctx["atr_daily"],
                          (" · " + ", ".join(ctx["setups"])) if ctx["setups"] else ""), ctx))

    # 3. news
    news, err = headlines(48, now_utc)
    if news is None:
        steps.append(step("trader-news", "Actualités", "warn", "Flux indisponible : %s" % err))
    else:
        trade["news"] = news[:6]
        macro = sorted({t for n in news for t in n["tags"]})
        steps.append(step("trader-news", "Actualités", "warn" if macro else "ok",
                          "%d titres or/macro sur 48 h%s" % (
                              len(news), (" — thèmes : " + ", ".join(macro)) if macro else ""), news))

    # 4. entry
    bs = days[day]
    rng = opening_range(bs, sess, or_minutes)
    done = [b for b in bs if b[1] + 5 <= upto]
    trig = find_trigger(bs, rng, sess, or_minutes, upto, allow_short)
    trade["range"] = rng
    dates = sorted(days)
    prev = days[dates[dates.index(day) - 1]] if dates.index(day) else []
    if trig:
        trade["entry_status"] = "triggered"
        steps.append(step("trader-entry", "Signal (cassure du range %s)" % label, "ok",
                          "DÉCLENCHÉ %s : clôture 5 min à %s, %s range %s – %s (%02d:%02d)" % (
                              "ACHAT" if trig["side"] == "buy" else "VENTE", trig["price"],
                              "au-dessus du" if trig["side"] == "buy" else "sous le",
                              rng["low"], rng["high"], *divmod(trig["minute"], 60))))
        cands = [(trig["side"], trig["price"], trig["index"], trig["minute"])]
    else:
        trade["entry_status"] = "waiting"
        last = done[-1][5] if done else None
        steps.append(step("trader-entry", "Signal (cassure du range %s)" % label, "warn",
                          "EN ATTENTE : range %s – %s, dernier cours %s. Ordres en attente des deux côtés." % (
                              rng["low"], rng["high"], last)))
        idx = len(done) - 1
        cands = [("buy", rng["high"], idx, upto)] + ([("sell", rng["low"], idx, upto)] if allow_short else [])

    # 5-9 for each side
    hist = history(days, day, sess, or_minutes, stop_rule, target_r, allow_short)
    trade["history"] = hist
    sides = []
    for side, entry, idx, minute in cands:
        a5 = atr5(bs, max(idx, 0), prev)
        lv = make_levels(side, entry, rng, stop_rule, target_r, a5)
        if not lv:
            steps.append(step("trader-exit", "Plan %s" % side, "fail", "Stop du mauvais côté de l'entrée"))
            continue
        tm = time_machine(days, day, lv, minute - minute % 5, sess)
        sz = size(lv, s, spread)
        verdict, reasons, info = risk_check(lv, sz, s, live, now_min, sess, market_ok)
        if mode == "rehearsal" and trig:
            out, r = walk(bs[idx + 1:], lv)
            lv["real_outcome"] = {"outcome": out, "R": r}
        if live and trig:
            since = [b for b in bs[idx + 1:] if b[1] + 5 <= upto]
            out, r = walk(since, lv)
            lv["now_price"] = last_px
            if out != "close":
                verdict = "BLOCK"
                reasons = reasons + ["déjà joué : %s touché depuis le signal" % (
                    "l'objectif" if out == "target" else "le stop")]
            elif abs(last_px - lv["entry"]) > lv["risk"] * 0.5:
                verdict = "BLOCK"
                reasons = reasons + ["le cours (%s) s'est éloigné de plus de 0,5R de l'entrée %s : trop tard"
                                     % (last_px, lv["entry"])]
            else:
                info.append("cours actuel %s, signal à %02d:%02d" % (last_px, *divmod(minute, 60)))
        b = {k: round(v + offset, 2) for k, v in lv.items() if k in ("entry", "stop", "target")}
        sides.append(dict(lv, tm=tm, size=sz, verdict=verdict, reasons=reasons, info=info,
                          broker=b, order=("BUY" if side == "buy" else "SELL")
                          + ("" if trig else " STOP")))
    trade["sides"] = sides

    def fmt_side(x):
        return "%s %s · stop %s · objectif %s" % ("Achat" if x["side"] == "buy" else "Vente",
                                                  x["entry"], x["stop"], x["target"])
    steps.append(step("trader-exit", "Plan de sortie", "ok" if sides else "fail",
                      " | ".join(fmt_side(x) for x in sides) + " · sortie forcée %s (%s)" % (flat, label),
                      [{k: x[k] for k in ("side", "entry", "stop", "target", "risk")} for x in sides]))
    tms = [x for x in sides if x["tm"]]
    steps.append(step("trader-timemachine", "Time Machine (10 000 replays)", "ok" if tms else "warn",
                      " | ".join("%s : objectif %.1f %%, stop %.1f %%, R moyen %+.2f" % (
                          "Achat" if x["side"] == "buy" else "Vente", x["tm"]["p_target"] * 100,
                          x["tm"]["p_stop"] * 100, x["tm"]["avg_R"]) for x in tms)
                      + " · Historique %d séances : %d signaux, %d objectifs, %d stops, R moyen %s" % (
                          hist["sessions"], hist["triggered"], hist["target"], hist["stop"], hist["avg_R"]),
                      {"replays": [x["tm"] for x in sides], "history": hist}))
    steps.append(step("trader-budget", "Taille en lots", "ok" if all(x["size"].get("lots") for x in sides) else "fail",
                      " | ".join(("%s : %.2f lot (%g oz), marge %.2f $, levier effectif %.2fx, perte max %.2f $"
                                  % ("Achat" if x["side"] == "buy" else "Vente", x["size"]["lots"], x["size"]["oz"],
                                     x["size"]["margin"], x["size"]["leverage_used"], x["size"]["max_loss"]))
                                 if x["size"].get("lots") else x["size"].get("refusal", "?") for x in sides),
                      [x["size"] for x in sides]))
    steps.append(step("trader-risk", "Contrôle du risque",
                      "ok" if sides and all(x["verdict"] == "PASS" for x in sides) else "fail",
                      " | ".join("%s %s%s" % ("Achat" if x["side"] == "buy" else "Vente", x["verdict"],
                                              (" — " + "; ".join(x["reasons"])) if x["reasons"] else "")
                                 for x in sides)))
    tickets = ["%s XAUUSD %.2f lot @ %.2f  SL %.2f  TP %.2f  (annuler / clôturer à %s %s)" % (
        x["order"], x["size"].get("lots", 0), x["broker"]["entry"], x["broker"]["stop"],
        x["broker"]["target"], flat, label) for x in sides if x["size"].get("lots")]
    if len(tickets) == 2:
        tickets.append("Les deux ordres sont liés (OCO) : quand l'un est exécuté, annule l'autre.")
    if offset:
        tickets.append("Niveaux décalés de %+.2f $ (ton prix broker - GC=F)." % offset)
    else:
        tickets.append("Niveaux GC=F (futures). Renseigne ton prix XAUUSD broker pour les caler sur le spot.")
    steps.append(step("trader-broker", "Ticket (non envoyé)", "ok" if sides else "skip",
                      "À saisir toi-même chez ton broker (MT4/MT5…). Rien n'est envoyé d'ici.",
                      text="\n".join(tickets)))
    trade["tickets"] = tickets
    steps.append(step("trader-alerts", "Alertes", "ok",
                      "Niveaux à surveiller : " + ", ".join("stop %s / objectif %s" % (x["broker"]["stop"], x["broker"]["target"])
                                                          for x in sides) + ", sortie forcée %s %s" % (flat, label)))
    steps.append(step("trader-analyst", "Résultats d'entreprise", "skip", "Sans objet pour l'or"))
    steps.append(step("trader-pelosi", "Transactions du Congrès", "skip", "Sans objet pour l'or (bouton Congrès en haut)"))

    ok = [x for x in sides if x["verdict"] == "PASS"]
    if live and trig and ok:
        trade.update(headline="Signal déclenché, risque validé", level="go")
    elif ok:
        trade.update(headline=("Ordres en attente prêts" if not trig else "Signal déclenché")
                     + ("" if live else " (répétition)"), level="wait")
    elif sides:
        trade.update(headline="Bloqué par le contrôle du risque", level="bad")
    else:
        trade.update(headline="Pas de trade sur cette règle", level="none")
    return {"symbol": "XAUUSD", "mode": mode, "steps": steps, "trade": trade}


if __name__ == "__main__":
    import sys
    s = {"capital": 5000, "risk_pct": 1, "target": "2R", "xau_leverage": 20}
    if len(sys.argv) > 1:
        s["xau_session"] = sys.argv[1]
    r = analyze(s)
    print(json.dumps(r, indent=1, default=str)[:6000])
