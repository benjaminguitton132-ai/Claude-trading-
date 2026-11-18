#!/usr/bin/env python3
"""Trading Desk: a small local web app that runs the 11 trader-* skills.

Standard library only. Start it with:

    python3 app/server.py            # then open http://localhost:8765

Each analysis runs in its own folder under app/runs/, so runs never mix.
Nothing here can place an order: the broker step only renders the ticket.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
SKILLS = ROOT / ".claude" / "skills"
RUNS = APP / "runs"
SETTINGS = APP / "settings.json"
PORT = int(os.environ.get("PORT", "8765"))
PY = sys.executable or "python3"

DEFAULTS = {
    "capital": 5000,          # fonds disponibles, $
    "risk_pct": 1.0,          # perte max par trade, % du capital
    "daily_loss_pct": 3.0,    # perte max sur la journée, % du capital
    "leverage": 1,            # levier max autorisé (1 = pas de marge)
    "stop": "or-mid",         # or-mid, or-low, pct:1, ...
    "target": "2R",
    "max_trades_per_day": 3,
    "sec_user_agent": "",     # "Nom email" pour la SEC (news 8-K, analyst)
}

SCRIPTS = {
    "scanner": "trader-scanner/scan.py",
    "news": "trader-news/news.py",
    "entry": "trader-entry/entry.py",
    "exit": "trader-exit/exit.py",
    "timemachine": "trader-timemachine/timemachine.py",
    "budget": "trader-budget/size.py",
    "risk": "trader-risk/check.py",
    "broker": "trader-broker/ticket.py",
    "alerts": "trader-alerts/alerts.py",
    "analyst": "trader-analyst/facts.py",
    "pelosi": "trader-pelosi/ptr.py",
}

SYMBOL_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


# ---------------------------------------------------------------- settings

def load_settings():
    s = dict(DEFAULTS)
    try:
        s.update(json.loads(SETTINGS.read_text()))
    except (OSError, ValueError):
        pass
    return s


def save_settings(new):
    s = load_settings()
    for k in DEFAULTS:
        if k in new:
            s[k] = new[k]
    s["capital"] = max(100.0, float(s["capital"]))
    s["risk_pct"] = min(max(0.1, float(s["risk_pct"])), 5.0)
    s["daily_loss_pct"] = min(max(0.1, float(s["daily_loss_pct"])), 20.0)
    s["leverage"] = min(max(1.0, float(s["leverage"])), 4.0)
    s["max_trades_per_day"] = int(s["max_trades_per_day"])
    SETTINGS.write_text(json.dumps(s, indent=2))
    return s


def pack_config(s):
    """The trader/config.json the skills read, built from the app settings."""
    cap, lev = float(s["capital"]), float(s["leverage"])
    budget = round(cap * lev, 2)
    return {
        "budget": budget,
        "cash_buffer_pct": 5,
        "max_position_pct": 95,
        "max_order_usd": round(budget * 0.95, 2),
        "min_order_usd": 5,
        "max_loss_per_trade_usd": round(cap * float(s["risk_pct"]) / 100, 2),
        "max_daily_loss_usd": round(cap * float(s["daily_loss_pct"]) / 100, 2),
        "max_trades_per_day": int(s["max_trades_per_day"]),
        "max_orders_per_day": 10,
        "min_reward_risk": 1.0,
        "require_stop": True,
        "no_entries_before": "09:45",
        "no_entries_after": "15:30",
        "flat_by": "15:55",
        "fractional": False,
        "broker": "alpaca",
        "paper": True,
        "blocked": [],
        "allow_options": False,
        "allow_margin": lev > 1,
        "allow_short": False,
        "pdt_guard": False,
        "sec_user_agent": s.get("sec_user_agent") or "",
    }


# ---------------------------------------------------------------- running

def run(name, args, cwd, timeout=180):
    """Run one skill script; return (exit code, stdout, stderr)."""
    cmd = [PY, str(SKILLS / SCRIPTS[name])] + [str(a) for a in args]
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout after %ds" % timeout


def run_json(name, args, cwd, timeout=180):
    code, out, err = run(name, list(args) + ["--json"], cwd, timeout)
    try:
        return code, json.loads(out), err
    except ValueError:
        return code, None, (err or out).strip()


def step(skill, title, status, summary, data=None, text=""):
    return {"skill": skill, "title": title, "status": status, "summary": summary,
            "data": data, "text": (text or "").strip()[-6000:]}


def floor_bar(hhmm):
    h, m = map(int, hhmm.split(":"))
    m = m - m % 5
    return "%d:%02d %s" % (h if h <= 12 else h - 12, m, "PM" if h >= 12 else "AM")


def money(x):
    return "${:,.2f}".format(x)


def analyze(symbol, s):
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.match(symbol):
        return {"symbol": symbol, "error": "Ticker invalide : %s" % symbol}

    wd = RUNS / ("%s-%s" % (datetime.now().strftime("%Y%m%d-%H%M%S-%f"), symbol))
    (wd / "trader").mkdir(parents=True, exist_ok=True)
    cfg = pack_config(s)
    (wd / "trader" / "config.json").write_text(json.dumps(cfg, indent=2))
    steps, trade = [], {"symbol": symbol}

    # 1. Alerts: the NYSE clock decides live vs rehearsal ------------------
    _, clock, err = run_json("alerts", ["clock"], wd)
    now_flag, mode = [], "live"
    if not clock:
        steps.append(step("trader-alerts", "Horloge NYSE", "fail", "Horloge indisponible", text=err))
        clock = {}
    live = clock.get("open") and clock.get("now_new_york", "")[-5:] >= "09:50"

    # The entry timer tells us the last session with data.
    _, probe, err = run_json("entry", ["check", symbol, "--setup", "orb"], wd)
    if not probe:
        steps.append(step("trader-entry", "Données", "fail",
                          "Pas de données Yahoo pour %s" % symbol, text=err))
        return {"symbol": symbol, "steps": steps, "trade": None, "mode": None,
                "error": "Pas de données pour %s (ticker inconnu ou réseau bloqué)." % symbol}
    if live:
        now_txt = clock["now_new_york"]
        bar_time = floor_bar(now_txt[-5:])
    else:
        mode = "rehearsal"
        last_day = (probe.get("data_time") or "")[:10] or clock.get("date")
        # Same calendar day before the open: the data is yesterday's, fine.
        now_txt = "%s 10:15" % last_day
        now_flag = ["--now", now_txt]
        bar_time = "10:15 AM"
    trade.update(mode=mode, as_of=now_txt)

    if clock:
        if live:
            msg = "Marché ouvert (%s New York) : analyse en direct." % clock["now_new_york"][-5:]
        else:
            msg = ("Marché %s (%s New York). Répétition sur la dernière séance (%s à 10h15) : "
                   "les niveaux seront à recalculer à l'ouverture." % (
                       "fermé" if not clock.get("open") else "ouvert mais range pas encore fini",
                       clock.get("now_new_york", "?")[-5:], now_txt[:10]))
        steps.append(step("trader-alerts", "Horloge NYSE", "ok", msg, clock))

    # 2. Scanner: daily setups on this symbol --------------------------------
    _, sc, err = run_json("scanner", ["daily", "--symbols", symbol, "--no-write", "--min-volume", "0"], wd)
    if sc is not None:
        hits = sc.get("hits") or []
        setups = hits[0].get("setups", []) if hits else []
        names = {"breakout_20d": "plus haute clôture 20 j", "bull_flag": "drapeau haussier",
                 "reclaim_ma20": "repasse la moyenne 20 j", "oversold": "survendu (RSI<30)",
                 "oversold_bounce": "rebond après survente"}
        trade["setups"] = [names.get(x, x) for x in setups]
        rsi = hits[0].get("rsi") if hits else None
        steps.append(step("trader-scanner", "Scanner (journalier)", "ok",
                          ("Règles déclenchées : " + ", ".join(trade["setups"])) if setups
                          else "Aucune des 5 règles journalières ne se déclenche"
                          + (" (RSI %.1f)" % rsi if rsi else ""), sc))
    else:
        steps.append(step("trader-scanner", "Scanner (journalier)", "warn", "Scan indisponible", text=err))

    # 3. News -----------------------------------------------------------------
    news_args = ["--tickers", symbol, "--hours", "48", "--dry-run"]
    if not cfg["sec_user_agent"]:
        news_args.append("--no-sec")
    _, nw, err = run_json("news", news_args, wd, timeout=90)
    if nw is not None:
        items = nw.get("items") or []
        mv = (nw.get("moves") or [{}])[0]
        trade["news"] = [{"title": i.get("title"), "time": i.get("time"), "tags": i.get("tags"),
                          "link": i.get("link"), "kind": i.get("kind")} for i in items[:6]]
        flagged = [i for i in items if set(i.get("tags") or []) & {"earnings", "halt", "deal", "regulatory"}]
        summ = "%d titres sur 48 h" % len(items)
        if mv.get("pct") is not None:
            summ += ", %+.2f %% vs clôture précédente" % mv["pct"]
        if flagged:
            summ += " — ATTENTION : %s" % ", ".join(sorted({t for i in flagged for t in i["tags"]}))
        if not cfg["sec_user_agent"]:
            summ += " (8-K SEC ignorés : renseigne ton nom + email dans Réglages)"
        steps.append(step("trader-news", "Actualités", "warn" if flagged else "ok", summ, nw))
    else:
        steps.append(step("trader-news", "Actualités", "warn", "Actualités indisponibles", text=err))

    # 4. Entry ----------------------------------------------------------------
    _, en, err = run_json("entry", ["check", symbol, "--setup", "orb", "--write"] + now_flag, wd)
    plan_args = None
    if en:
        st, orng = en.get("status"), en.get("opening_range") or {}
        trade["entry_status"] = st
        if st == "triggered":
            trig = en.get("trigger") or {}
            summ = "DÉCLENCHÉ : clôture au-dessus du range à %s (%s)" % (
                trig.get("close", "?"), trig.get("time", "?"))
            plan_args = ["plan", "--stop", s["stop"], "--target", s["target"]]
            stt = "ok"
        elif st == "waiting" and orng.get("high"):
            summ = "EN ATTENTE : il faut une clôture 5 min au-dessus de %s (range %s – %s)" % (
                orng["high"], orng.get("low"), orng["high"])
            plan_args = ["plan", "--entry", orng["high"], "--stop", s["stop"], "--target", s["target"]]
            stt = "warn"
        else:
            summ = "%s : %s" % ((st or "?").upper(), en.get("reason") or "pas de signal exploitable")
            stt = "warn"
        steps.append(step("trader-entry", "Signal d'entrée (cassure du range d'ouverture)", stt, summ, en))
    else:
        steps.append(step("trader-entry", "Signal d'entrée", "fail", "Échec", text=err))

    # 5. Exit -----------------------------------------------------------------
    plan = None
    if plan_args:
        _, plan, err = run_json("exit", plan_args + ["--write"] + now_flag, wd)
        if plan:
            trade.update(entry=plan["entry"], stop=plan["stop"], target=plan["target"],
                         risk_per_share=plan["risk_per_share"], reward_risk=plan["reward_risk"],
                         flat_by=plan.get("flat_by"), stop_label=plan.get("stop_label"),
                         target_label=plan.get("target_label"))
            steps.append(step("trader-exit", "Plan de sortie", "ok",
                              "Entrée %s · stop %s · objectif %s · R:R %.1f · clôturé avant %s" % (
                                  plan["entry"], plan["stop"], plan["target"],
                                  plan["reward_risk"], plan.get("flat_by")), plan))
        else:
            steps.append(step("trader-exit", "Plan de sortie", "fail", "Plan refusé", text=err))
    else:
        steps.append(step("trader-exit", "Plan de sortie", "skip", "Pas de signal, pas de plan"))

    # 6. Time machine ---------------------------------------------------------
    if plan:
        tm_args = ["run", "--write"] + now_flag
        if not plan.get("entry_time") and not plan.get("entry_bar"):
            tm_args += ["--symbol", symbol, "--date", now_txt[:10], "--entry", plan["entry"],
                        "--stop", plan["stop"], "--target", plan["target"],
                        "--entry-time", bar_time, "--setup", "orb"]
        _, tm, err = run_json("timemachine", tm_args, wd, timeout=300)
        if tm:
            mc, hist = tm.get("mc") or {}, tm.get("history") or {}
            trade["odds"] = {k: mc.get("p_" + k) for k in ("target", "stop", "neither", "green")}
            trade["avg_r"] = mc.get("avg_R")
            trade["close_band"] = [mc.get("p5_close"), mc.get("median_close"), mc.get("p95_close")]
            trade["history"] = {k: hist.get(k) for k in ("sessions", "triggered", "target", "stop", "close", "avg_R")}
            trade["verdict_tm"] = tm.get("verdict")
            steps.append(step("trader-timemachine", "Time Machine (10 000 replays)", "ok",
                              tm.get("verdict") or "", tm))
        else:
            steps.append(step("trader-timemachine", "Time Machine", "warn", "Simulation impossible", text=err))
    else:
        steps.append(step("trader-timemachine", "Time Machine", "skip", "Pas de plan à simuler"))

    # 7. Budget ---------------------------------------------------------------
    orders_ok = False
    if plan:
        _, bd, err = run_json("budget", ["--write"] + now_flag, wd)
        sz = (bd or {}).get("sizing") or {}
        if sz.get("qty"):
            orders_ok = True
            cost = sz["cost"]
            trade.update(qty=sz["qty"], cost=cost, max_loss=sz["max_loss"],
                         gain_at_target=round(sz["qty"] * (plan["target"] - sz["entry"]), 2),
                         leverage_used=round(cost / float(s["capital"]), 2),
                         bound_by=sz.get("bound_by"))
            steps.append(step("trader-budget", "Taille de position", "ok",
                              "%d × %s = %s · perte max au stop %s · levier effectif %.2fx (limite : %s)" % (
                                  sz["qty"], symbol, money(cost), money(sz["max_loss"]),
                                  trade["leverage_used"], sz.get("bound_by")), bd))
        else:
            steps.append(step("trader-budget", "Taille de position", "fail",
                              (sz.get("refusal") or err or "Taille impossible"), bd, text=err))
    else:
        steps.append(step("trader-budget", "Taille de position", "skip", "Pas de plan"))

    # 8. Risk -----------------------------------------------------------------
    if orders_ok:
        _, rk, err = run_json("risk", now_flag, wd)
        r = ((rk or {}).get("results") or [{}])[0]
        trade["risk_verdict"] = r.get("verdict")
        trade["risk_reasons"] = r.get("reasons") or []
        steps.append(step("trader-risk", "Contrôle du risque", "ok" if r.get("verdict") == "PASS" else "fail",
                          (r.get("verdict") or "?") + ((" — " + "; ".join(r.get("reasons"))) if r.get("reasons") else ""),
                          rk, text=err))
    else:
        steps.append(step("trader-risk", "Contrôle du risque", "skip", "Aucun ordre à contrôler"))

    # 9. Broker (ticket only, never places) -----------------------------------
    if orders_ok:
        code, out, err = run("broker", ["show"] + now_flag, wd)
        steps.append(step("trader-broker", "Ticket (non envoyé)", "ok",
                          "Ticket prêt. Rien n'est envoyé : pour le passer (paper), demande-le à Claude et confirme par « oui ».",
                          text=out or err))
    else:
        steps.append(step("trader-broker", "Ticket", "skip", "Pas d'ordre"))

    # 10. Alerts from the plan ------------------------------------------------
    if plan:
        code, out, err = run("alerts", ["add", "--from-plan"], wd)
        steps.append(step("trader-alerts", "Alertes", "ok" if code == 0 else "warn",
                          "Stop %s, objectif %s, sortie forcée à %s" % (plan["stop"], plan["target"], plan.get("flat_by")),
                          text=out or err))

    # 11. Analyst (stocks only, needs the SEC user agent) ---------------------
    if cfg["sec_user_agent"]:
        _, fa, err = run_json("analyst", [symbol, "--quarters", "4", "--no-filings"], wd, timeout=90)
        if fa:
            steps.append(step("trader-analyst", "Résultats trimestriels (SEC)", "ok",
                              "Chiffres SEC récupérés", fa))
        else:
            steps.append(step("trader-analyst", "Résultats trimestriels", "skip",
                              "Pas de comptes SEC (ETF, matière première ou société étrangère)", text=err))
    else:
        steps.append(step("trader-analyst", "Résultats trimestriels", "skip",
                          "Renseigne ton nom + email (SEC) dans Réglages pour l'activer"))

    # 12. Pelosi: not tied to one asset, there is a dedicated button ----------
    steps.append(step("trader-pelosi", "Transactions du Congrès", "skip",
                      "Indépendant de l'actif : bouton « Congrès » en haut"))

    # The headline -------------------------------------------------------------
    if trade.get("risk_verdict") == "PASS" and trade.get("entry_status") == "triggered" and live:
        trade["headline"] = "Signal déclenché, risque validé"
        trade["level"] = "go"
    elif trade.get("qty"):
        trade["headline"] = ("Plan prêt — en attente du signal" if trade.get("entry_status") != "triggered"
                             else "Signal déclenché") + (" (répétition, marché fermé)" if not live else "")
        if trade.get("risk_verdict") == "BLOCK" and live:
            trade["headline"] = "Bloqué par le contrôle du risque"
        trade["level"] = "wait"
    else:
        trade["headline"] = "Pas de trade sur cette règle"
        trade["level"] = "none"
    return {"symbol": symbol, "mode": mode, "steps": steps, "trade": trade, "run_dir": str(wd.relative_to(ROOT))}


def scan(kind):
    wd = RUNS / ("scan-%s" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    (wd / "trader").mkdir(parents=True, exist_ok=True)
    (wd / "trader" / "config.json").write_text(json.dumps(pack_config(load_settings())))
    uni = ROOT / "trader" / "universe.txt"
    if not uni.exists():
        (ROOT / "trader").mkdir(exist_ok=True)
        run("scanner", ["universe"], ROOT, timeout=120)
    if uni.exists():
        (wd / "trader" / "universe.txt").write_text(uni.read_text())
    args = [kind, "--no-write", "--quiet"] if kind == "daily" else [kind, "--no-write"]
    code, data, err = run_json("scanner", args, wd, timeout=600)
    if not data:
        return {"error": err or "Scan impossible (marché fermé ?)"}
    return {"as_of": data.get("as_of"), "counts": data.get("counts"),
            "hits": (data.get("hits") or [])[:40], "note": data.get("note")}


def congress():
    wd = RUNS / "congress"
    (wd / "trader").mkdir(parents=True, exist_ok=True)
    code, data, err = run_json("pelosi", ["index", "--member", "pelosi", "--limit", "15"], wd, timeout=120)
    return {"filings": data, "error": None if data is not None else err}


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def log_message(self, fmt, *args):
        sys.stderr.write("[desk] %s\n" % (fmt % args))

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, (APP / "index.html").read_bytes(), "text/html")
        if self.path == "/api/settings":
            return self._send(200, load_settings())
        if self.path == "/api/clock":
            code, data, err = run_json("alerts", ["clock"], APP)
            return self._send(200, data or {"error": err})
        if self.path == "/api/congress":
            return self._send(200, congress())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        b = self._body()
        if self.path == "/api/settings":
            return self._send(200, save_settings(b))
        if self.path == "/api/analyze":
            s = load_settings()
            syms = [x for x in (b.get("symbols") or []) if x][:8]
            t0 = time.time()
            results = [analyze(x, s) for x in syms]
            return self._send(200, {"results": results, "seconds": round(time.time() - t0, 1),
                                    "settings": s})
        if self.path == "/api/scan":
            return self._send(200, scan("orb" if b.get("kind") == "orb" else "daily"))
        self._send(404, {"error": "not found"})


def main():
    RUNS.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("Trading Desk sur http://localhost:%d  (Ctrl+C pour arrêter)" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
