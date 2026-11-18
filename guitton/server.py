#!/usr/bin/env python3
"""GUITTON: XAUUSD only.

    python3 guitton/server.py        # then open http://localhost:8800
    python3 guitton/server.py --lan  # also reachable from a phone on the same Wi-Fi

Standard library only (Python 3.9+). Nothing here can place an order.
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
from feed import FEED  # noqa: E402

PORT = int(os.environ.get("PORT", "8800"))
SETTINGS = HERE / "settings.json"
TRADE = HERE / "trade.json"
DEFAULTS = {"capital": 5000, "risk_pct": 1.0, "leverage": 20, "tp2_r": 2.0, "stop": "or-mid"}


def load(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def settings():
    s = dict(DEFAULTS)
    s.update(load(SETTINGS, {}))
    return s


def save_settings(b):
    s = settings()
    try:
        s["capital"] = max(100.0, float(b.get("capital", s["capital"])))
        s["risk_pct"] = min(max(0.1, float(b.get("risk_pct", s["risk_pct"]))), 5.0)
        s["leverage"] = min(max(1, int(float(b.get("leverage", s["leverage"])))), 500)
        s["tp2_r"] = min(max(1.5, float(b.get("tp2_r", s["tp2_r"]))), 5.0)
    except (TypeError, ValueError):
        pass
    if b.get("stop") in ("or-mid", "or-opp", "atr:2", "pct:0.3"):
        s["stop"] = b["stop"]
    SETTINGS.write_text(json.dumps(s, indent=2))
    return s


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self.send(200, (HERE / "index.html").read_bytes(), "text/html")
        if p == "/api/price":
            b, ok = FEED.basis()
            return self.send(200, {"price": FEED.price(), "basis": b, "basis_ok": ok,
                                   "error": FEED.error, "server_time": time.time()})
        if p == "/api/candles":
            return self.send(200, {"candles": FEED.candles(150)})
        if p == "/api/settings":
            return self.send(200, settings())
        if p == "/api/trade":
            return self.send(200, load(TRADE, None))
        self.send(404, {"error": "not found"})

    def do_POST(self):
        p, b = self.path, self.body()
        if p == "/api/settings":
            return self.send(200, save_settings(b))
        if p == "/api/analyze":
            try:
                return self.send(200, engine.analyze(settings(), FEED))
            except Exception as e:  # noqa: BLE001
                return self.send(200, {"status": "error", "headline": "Erreur d'analyse", "detail": str(e),
                                       "agents": []})
        if p == "/api/trade":
            if b.get("clear"):
                TRADE.unlink(missing_ok=True)
                return self.send(200, None)
            TRADE.write_text(json.dumps(b.get("trade"), indent=2))
            return self.send(200, b.get("trade"))
        self.send(404, {"error": "not found"})


def lan_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main():
    FEED.start()
    lan = "--lan" in sys.argv
    srv = ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", PORT), H)
    print("GUITTON sur http://localhost:%d  (Ctrl+C pour arrêter)" % PORT)
    if lan:
        ip = lan_ip()
        print("Sur ton téléphone (même Wi-Fi) : http://%s:%d" % (ip or "<IP-du-PC>", PORT))
        print("Attention : toute personne sur ce Wi-Fi peut ouvrir la page. À utiliser chez toi uniquement.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
