"""GUITTON analysis: 11 agents, one XAUUSD trade proposal.

  1 Horloge      which session window is open (London / New York)
  2 Contexte     daily trend, RSI, ATR, 20-day highs and lows       (trader-scanner)
  3 Actualités   gold and macro headlines                           (trader-news)
  4 Macro        dollar index and US 10-year yield, gold's two drivers (trader-analyst)
  5 Entrée       opening-range breakout on 5-minute bars            (trader-entry)
  6 Sortie       stop, TP1, TP2                                     (trader-exit)
  7 Time Machine 10,000 replays + the rule's history                (trader-timemachine)
  8 Budget       lots from capital, risk and broker leverage        (trader-budget)
  9 Risque       PASS / BLOCK                                       (trader-risk)
 10 Ticket       the order to type at the broker, never sent        (trader-broker)
 11 Alertes      the levels the live monitor watches                (trader-alerts)

Levels are computed on GC=F and converted to spot XAUUSD with the live basis.
"""
import json
import math
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import xau_core as X

UTC = timezone.utc
PARIS = ZoneInfo("Europe/Paris")
OZ = 100
OR_MIN = 15
ZONE_R = 0.2      # entry zone: entry +- 0.2 R
LATE_R = 0.5      # beyond entry + 0.5 R the trade is too late
WINDOWS = {       # session: (tz, entries from, entries until)
    "london": ("Europe/London", "08:20", "12:00"),
    "ny": ("America/New_York", "08:40", "12:00"),
}


def yahoo_daily(sym):
    url = "https://query2.finance.yahoo.com/v8/finance/chart/%s?range=1mo&interval=1d" % sym
    req = urllib.request.Request(url, headers={"User-Agent": X.UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())["chart"]["result"][0]
    closes = [c for c in d["indicators"]["quote"][0]["close"] if c is not None]
    return closes


def window_now(now_utc):
    """(session or None, next window text) for the London / New York entry windows."""
    for s, (tz, a, b) in WINDOWS.items():
        loc = now_utc.astimezone(ZoneInfo(tz))
        m = loc.hour * 60 + loc.minute
        if loc.weekday() < 5 and X.hm(a) <= m < X.hm(b):
            return s, None
    # the next window, in Paris time
    cands = []
    for s, (tz, a, b) in WINDOWS.items():
        z = ZoneInfo(tz)
        loc = now_utc.astimezone(z)
        for k in range(0, 8):
            d = (loc + timedelta(days=k)).date()
            start = datetime(d.year, d.month, d.day, *map(int, a.split(":")), tzinfo=z)
            if start > now_utc and start.weekday() < 5:
                cands.append((start, s))
                break
    start, s = min(cands)
    p = start.astimezone(PARIS)
    names = {"london": "Londres", "ny": "New York"}
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    same = p.date() == now_utc.astimezone(PARIS).date()
    return None, "%s, %s%s à %s (heure de Paris)" % (
        names[s], "" if same else jours[p.weekday()] + " ", "aujourd'hui" if same else "", p.strftime("%Hh%M"))


def agent(n, name, skill, status, summary):
    return {"n": n, "name": name, "skill": skill, "status": status, "summary": summary}


def plan_side(side, entry, rng, stop_rule, tp2_r, a5, spread, s):
    lv = X.make_levels(side, entry, rng, stop_rule, tp2_r, a5)
    if not lv:
        return None
    sgn = 1 if side == "buy" else -1
    R = lv["risk"]
    p = {"side": side, "entry": lv["entry"], "sl": lv["stop"], "R": R,
         "tp1": round(lv["entry"] + sgn * R, 2), "tp2": lv["target"],
         "zone": sorted([round(lv["entry"] - ZONE_R * R, 2), round(lv["entry"] + ZONE_R * R, 2)]),
         "late": round(lv["entry"] + sgn * LATE_R * R, 2), "tp2_r": tp2_r}
    # size on the worst fill inside the zone, spread included
    worst = p["zone"][1] if side == "buy" else p["zone"][0]
    per_oz = abs(worst - p["sl"]) + spread
    cap = float(s["capital"])
    risk_usd = cap * float(s["risk_pct"]) / 100
    lev = float(s["leverage"])
    lots = math.floor(risk_usd / (per_oz * OZ) * 100 + 1e-9) / 100
    max_lots = math.floor(cap * 0.5 * lev / (entry * OZ) * 100) / 100
    bound = "perte max"
    if max_lots < lots:
        lots, bound = max_lots, "marge (50 % du capital)"
    p.update(risk_budget=round(risk_usd, 2), spread=round(spread, 2), bound_by=bound)
    if lots < 0.01:
        p["refusal"] = ("Stop trop large pour ton risque : 0,01 lot perdrait %.2f $ (budget %.2f $)"
                        % (per_oz, risk_usd)) if bound == "perte max" else "Marge insuffisante pour 0,01 lot"
        return p
    notional = lots * OZ * entry
    p.update(lots=lots, margin=round(notional / lev, 2), lev_used=round(notional / cap, 2),
             max_loss=round(lots * OZ * per_oz, 2),
             gain_tp1_full=round(lots * OZ * (R - spread), 2),
             gain_tp2_full=round(lots * OZ * (tp2_r * R - spread), 2))
    # the plan the monitor follows: 50 % at TP1, the rest at TP2
    p["gain_plan"] = round(lots * OZ * 0.5 * (R - spread) + lots * OZ * 0.5 * (tp2_r * R - spread), 2)
    return p


def analyze(s, feed, now_utc=None):
    now_utc = now_utc or datetime.now(UTC)
    agents, conf = [], []
    out = {"now_paris": now_utc.astimezone(PARIS).strftime("%d/%m %H:%M"), "agents": agents,
           "confluence": conf}

    # 1. clock
    market_ok, why = X.futures_open(now_utc)
    sess, nxt = window_now(now_utc)
    names = {"london": "Londres", "ny": "New York"}
    out["session"] = names.get(sess)
    agents.append(agent(1, "Horloge", "trader-alerts", "ok" if (market_ok and sess) else "warn",
                        ("%s · fenêtre %s ouverte" % (why.capitalize(), names[sess])) if sess and market_ok
                        else "%s · aucune fenêtre d'entrée maintenant. Prochaine : %s" % (why.capitalize(), nxt)))

    # spot and basis
    px = feed.price()
    basis, calibrated = feed.basis()
    spread = px["spread"] if px else float(s.get("spread") or 0.5)
    out["price"], out["basis"], out["basis_ok"] = px, basis, calibrated

    # data
    try:
        bars, meta = X.chart("60d", "5m")
        daily, _ = X.chart("6mo", "1d")
    except RuntimeError as e:
        out.update(status="error", headline=str(e))
        return out

    # 2. context
    ctx = X.daily_context(daily)
    out["context"] = ctx
    agents.append(agent(2, "Contexte", "trader-scanner", "ok",
                        "Tendance %s · RSI %s · ATR jour %s $%s" % (
                            ctx["trend"], ctx["rsi"], ctx["atr_daily"],
                            (" · " + ", ".join(ctx["setups"])) if ctx["setups"] else "")))

    # 3. news
    news, err = X.headlines(24, now_utc)
    macro_tags = sorted({t for n in (news or []) for t in n["tags"]})
    out["news"] = (news or [])[:5]
    agents.append(agent(3, "Actualités", "trader-news", "warn" if macro_tags else "ok",
                        ("%d titres or/macro sur 24 h" % len(news) + (" · thèmes : " + ", ".join(macro_tags) if macro_tags else ""))
                        if news is not None else "Flux indisponible"))

    # 4. macro: dollar and yields
    macro = {}
    try:
        dx, tnx = yahoo_daily("DX-Y.NYB"), yahoo_daily("%5ETNX")
        macro = {"dxy": round(dx[-1], 2), "dxy_chg": round((dx[-1] / dx[-2] - 1) * 100, 2),
                 "us10y": round(tnx[-1], 3), "us10y_chg": round(tnx[-1] - tnx[-2], 3)}
        bias = -1 if (macro["dxy_chg"] > 0.15 or macro["us10y_chg"] > 0.03) else (
            1 if (macro["dxy_chg"] < -0.15 or macro["us10y_chg"] < -0.03) else 0)
        macro["bias"] = bias
        agents.append(agent(4, "Macro", "trader-analyst", "ok",
                            "Dollar %s (%+.2f %%) · taux US 10 ans %s %% (%+.3f) → %s pour l'or" % (
                                macro["dxy"], macro["dxy_chg"], macro["us10y"], macro["us10y_chg"],
                                {1: "favorable", -1: "défavorable", 0: "neutre"}[bias])))
    except Exception as e:  # noqa: BLE001
        agents.append(agent(4, "Macro", "trader-analyst", "warn", "Dollar / taux indisponibles"))
    out["macro"] = macro

    # 5. entry
    use = sess or s.get("session") or "london"
    days = X.sessions(bars, use, OR_MIN)
    tz = ZoneInfo(X.SESSIONS[use][0])
    loc = now_utc.astimezone(tz)
    today, now_min = loc.date().isoformat(), loc.hour * 60 + loc.minute
    if not sess or not market_ok or today not in days or not X.opening_range(days[today], use, OR_MIN):
        # no live window: show the rule's track record and stop here
        hist = X.history(days, today, use, OR_MIN, s.get("stop") or "or-mid", float(s["tp2_r"]), True)
        out["history"] = hist
        for n, name, sk in ((5, "Entrée", "trader-entry"), (6, "Sortie", "trader-exit")):
            agents.append(agent(n, name, sk, "skip", "Pas de range d'ouverture en cours"))
        agents.append(agent(7, "Time Machine", "trader-timemachine", "ok",
                            "Historique %s : %d signaux sur %d séances, %d TP2, %d SL, R moyen %s" % (
                                names[use], hist["triggered"], hist["sessions"], hist["target"], hist["stop"], hist["avg_R"])))
        for n, name, sk in ((8, "Budget", "trader-budget"), (9, "Risque", "trader-risk"),
                            (10, "Ticket", "trader-broker"), (11, "Alertes", "trader-alerts")):
            agents.append(agent(n, name, sk, "skip", "Rien à calculer hors fenêtre"))
        out.update(status="none", headline="Pas de trade maintenant",
                   detail="Prochaine fenêtre : %s. Relance l'analyse à ce moment-là." % nxt)
        return out

    bs = days[today]
    rng = X.opening_range(bs, use, OR_MIN)
    trig = X.find_trigger(bs, rng, use, OR_MIN, now_min, True)
    dates = sorted(days)
    prev = days[dates[dates.index(today) - 1]] if dates.index(today) else []
    stop_rule, tp2_r = s.get("stop") or "or-mid", float(s["tp2_r"])
    spot_rng = {"high": round(rng["high"] - basis, 2), "low": round(rng["low"] - basis, 2)}
    out["range"] = spot_rng
    if trig:
        cands = [(trig["side"], trig["price"], trig["index"], trig["minute"])]
        agents.append(agent(5, "Entrée", "trader-entry", "ok",
                            "Cassure %s du range %s – %s à %02d:%02d (clôture 5 min %s)" % (
                                "haussière" if trig["side"] == "buy" else "baissière",
                                spot_rng["low"], spot_rng["high"], *divmod(trig["minute"], 60),
                                round(trig["price"] - basis, 2))))
    else:
        done = [b for b in bs if b[1] + 5 <= now_min]
        idx = len(done) - 1
        cands = [("buy", rng["high"], idx, now_min), ("sell", rng["low"], idx, now_min)]
        agents.append(agent(5, "Entrée", "trader-entry", "warn",
                            "Pas encore de cassure : range %s – %s. Deux scénarios en attente." % (
                                spot_rng["low"], spot_rng["high"])))

    hist = X.history(days, today, use, OR_MIN, stop_rule, tp2_r, True)
    out["history"] = hist
    plans = []
    for side, entry, idx, minute in cands:
        a5 = X.atr5(bs, max(idx, 0), prev)
        p = plan_side(side, entry, rng, stop_rule, tp2_r, a5, spread, s)
        if not p:
            continue
        lv = {"side": side, "entry": p["entry"], "stop": p["sl"], "target": p["tp2"], "risk": p["R"]}
        tm2 = X.time_machine(days, today, lv, minute - minute % 5, use)
        tm1 = X.time_machine(days, today, dict(lv, target=p["tp1"]), minute - minute % 5, use)
        p["odds"] = {"tp1": tm1 and tm1["p_target"], "tp2": tm2 and tm2["p_target"],
                     "sl": tm1 and tm1["p_stop"], "avg_R": tm2 and tm2["avg_R"]}
        # to spot terms
        for k in ("entry", "sl", "tp1", "tp2", "late"):
            p[k] = round(p[k] - basis, 2)
        p["zone"] = [round(z - basis, 2) for z in p["zone"]]
        # risk check
        reasons = []
        if p.get("refusal"):
            reasons.append(p["refusal"])
        if now_min > X.hm(WINDOWS[use][2]):
            reasons.append("fenêtre d'entrée fermée")
        sgn = 1 if side == "buy" else -1
        if trig and px:
            since = [b for b in bs[idx + 1:] if b[1] + 5 <= now_min]
            res, _ = X.walk(since, lv)
            if res != "close":
                reasons.append("déjà joué : %s touché depuis le signal" % ("TP2" if res == "target" else "le SL"))
            elif (px["mid"] - p["late"]) * sgn > 0:
                reasons.append("trop tard : le prix (%s) a dépassé la zone de plus de 0,5R" % px["mid"])
            elif (px["mid"] - p["sl"]) * sgn <= 0:
                reasons.append("le prix est déjà au-delà du SL")
            elif (px["mid"] - (spot_rng["high"] if sgn > 0 else spot_rng["low"])) * sgn < 0:
                reasons.append("cassure annulée : le prix (%s) est revenu dans le range" % px["mid"])
        p["verdict"] = "BLOCK" if reasons else "PASS"
        p["reasons"] = reasons
        # confluence
        trend_ok = (ctx["trend"] == "haussière") if side == "buy" else (ctx["trend"] == "baissière")
        p["confluence"] = [
            {"label": "Tendance jour dans le sens du trade", "ok": trend_ok},
            {"label": "Macro (dollar / taux) favorable", "ok": macro.get("bias", 0) == sgn},
            {"label": "Time Machine : R moyen positif", "ok": bool(p["odds"]["avg_R"] and p["odds"]["avg_R"] > 0)},
            {"label": "Historique de la règle positif", "ok": bool(hist["avg_R"] and hist["avg_R"] > 0)},
        ]
        p["score"] = sum(c["ok"] for c in p["confluence"])
        p["ticket"] = "%s%s XAUUSD %.2f lot @ %.2f  SL %.2f  TP1 %.2f (50 %%)  TP2 %.2f" % (
            "BUY" if side == "buy" else "SELL", "" if trig else " STOP", p.get("lots", 0),
            p["entry"], p["sl"], p["tp1"], p["tp2"])
        plans.append(p)

    def lab(p):
        return "Achat" if p["side"] == "buy" else "Vente"
    agents.append(agent(6, "Sortie", "trader-exit", "ok",
                        " | ".join("%s : SL %s · TP1 %s · TP2 %s" % (lab(p), p["sl"], p["tp1"], p["tp2"]) for p in plans)))
    agents.append(agent(7, "Time Machine", "trader-timemachine", "ok",
                        " | ".join("%s : TP1 %.0f %% · TP2 %.0f %% · SL avant TP1 %.0f %%" % (
                            lab(p), (p["odds"]["tp1"] or 0) * 100, (p["odds"]["tp2"] or 0) * 100,
                            (p["odds"]["sl"] or 0) * 100) for p in plans)
                        + " · historique : %d signaux, R moyen %s" % (hist["triggered"], hist["avg_R"])))
    agents.append(agent(8, "Budget", "trader-budget", "ok" if all(p.get("lots") for p in plans) else "fail",
                        " | ".join(("%s : %.2f lot · marge %.0f $ · perte max %.2f $" % (lab(p), p["lots"], p["margin"], p["max_loss"]))
                                   if p.get("lots") else p.get("refusal", "") for p in plans)))
    agents.append(agent(9, "Risque", "trader-risk", "ok" if any(p["verdict"] == "PASS" for p in plans) else "fail",
                        " | ".join("%s %s%s" % (lab(p), p["verdict"], (" — " + "; ".join(p["reasons"])) if p["reasons"] else "")
                                   for p in plans)))
    agents.append(agent(10, "Ticket", "trader-broker", "ok", " | ".join(p["ticket"] for p in plans)
                        + " · à saisir toi-même, rien n'est envoyé"))
    agents.append(agent(11, "Alertes", "trader-alerts", "ok",
                        "Surveillance en direct prête : zone, SL, TP1, TP2, BE, fin de session %s" % X.SESSIONS[use][3]))

    out["plans"] = plans
    out["flat_by"] = X.SESSIONS[use][3]
    out["flat_tz"] = X.SESSIONS[use][0]
    fh, fm = map(int, X.SESSIONS[use][3].split(":"))
    out["flat_by_ts"] = loc.replace(hour=fh, minute=fm, second=0, microsecond=0).timestamp()
    ok = [p for p in plans if p["verdict"] == "PASS"]
    if trig and ok:
        out.update(status="trade", headline="Trade proposé : %s XAUUSD" % lab(ok[0]).upper())
    elif ok:
        out.update(status="wait", headline="En attente de cassure",
                   detail="Deux ordres stop possibles. Si l'un se déclenche, annule l'autre.")
    else:
        out.update(status="invalid", headline="TRADE INVALIDE",
                   detail="; ".join(r for p in plans for r in p["reasons"]))
    return out
