"""Live XAUUSD price feed.

Spot: Swissquote's public bid/ask feed for XAU/USD, polled every 2 seconds.
History: Yahoo's GC=F (COMEX future) 1-minute bars, which run about 10 minutes
late and a few dollars above spot. The gap between the two (the basis) is
measured by matching each GC=F minute close with the spot tick at that time,
so the history can be drawn in spot terms.
Standard library only.
"""
import json
import statistics
import threading
import time
import urllib.request

SQ = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD"
YH = "https://%s.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=1m"
UA = "Mozilla/5.0 (compatible; guitton/1.0)"


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class Feed:
    def __init__(self, poll=2.0):
        self.poll = poll
        self.lock = threading.Lock()
        self.ticks = []          # (ts, bid, ask)
        self.gc = []             # (ts_open, o, h, l, c) GC=F 1m
        self.gc_meta = {}
        self.basis_samples = []  # gc - spot at the same minute
        self.error = None
        self.started = False

    # -------------------------------------------------------------- polling
    def start(self):
        if self.started:
            return
        self.started = True
        threading.Thread(target=self._spot_loop, daemon=True).start()
        threading.Thread(target=self._gc_loop, daemon=True).start()

    def _spot_loop(self):
        while True:
            try:
                d = _get(SQ)
                # the "elite" profile is the tightest spread, the closest to a raw quote
                best = None
                for feed in d:
                    for p in feed.get("spreadProfilePrices", []):
                        if best is None or (p["ask"] - p["bid"]) < (best[1] - best[0]):
                            best = (p["bid"], p["ask"], feed.get("ts"))
                if best:
                    ts = (best[2] or time.time() * 1000) / 1000.0
                    with self.lock:
                        if not self.ticks or ts > self.ticks[-1][0]:
                            self.ticks.append((ts, round(best[0], 3), round(best[1], 3)))
                        cutoff = time.time() - 8 * 3600
                        while self.ticks and self.ticks[0][0] < cutoff:
                            self.ticks.pop(0)
                    self.error = None
            except Exception as e:  # noqa: BLE001 - keep polling
                self.error = "flux spot : %s" % e
            time.sleep(self.poll)

    def _gc_loop(self):
        while True:
            for host in ("query2", "query1"):
                try:
                    d = _get(YH % host, timeout=20)["chart"]["result"][0]
                    q = d["indicators"]["quote"][0]
                    bars = [(t, q["open"][i], q["high"][i], q["low"][i], q["close"][i])
                            for i, t in enumerate(d["timestamp"])
                            if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])]
                    with self.lock:
                        self.gc, self.gc_meta = bars, d["meta"]
                    self._calibrate()
                    break
                except Exception:  # noqa: BLE001
                    continue
            time.sleep(30)

    def _calibrate(self):
        with self.lock:
            ticks, bars = list(self.ticks), list(self.gc)
        if not ticks:
            return
        samples = []
        for t, o, h, l, c in bars[-30:]:
            close_ts = t + 60
            near = [x for x in ticks if abs(x[0] - close_ts) <= 4]
            if near:
                x = min(near, key=lambda x: abs(x[0] - close_ts))
                samples.append(c - (x[1] + x[2]) / 2)
        if samples:
            with self.lock:
                self.basis_samples = (self.basis_samples + samples)[-60:]

    # -------------------------------------------------------------- reads
    def price(self):
        with self.lock:
            t = self.ticks[-1] if self.ticks else None
        if not t:
            return None
        return {"ts": t[0], "bid": t[1], "ask": t[2], "mid": round((t[1] + t[2]) / 2, 2),
                "spread": round(t[2] - t[1], 3), "age": round(time.time() - t[0], 1)}

    def basis(self):
        """GC=F minus spot: (value, calibrated?)."""
        with self.lock:
            s = list(self.basis_samples)
            gc_last = self.gc[-1][4] if self.gc else None
        if len(s) >= 3:
            return round(statistics.median(s), 2), True
        p = self.price()
        if p and gc_last:
            return round(gc_last - p["mid"], 2), False   # rough: GC=F is ~10 min late
        return 0.0, False

    def candles(self, minutes=120):
        """1-minute candles in spot terms: GC=F history shifted by the basis, then spot ticks."""
        b, _ = self.basis()
        now = time.time()
        with self.lock:
            ticks, bars = list(self.ticks), list(self.gc)
        live = {}
        for ts, bid, ask in ticks:
            m = int(ts // 60) * 60
            mid = (bid + ask) / 2
            c = live.get(m)
            if c is None:
                live[m] = [m, mid, mid, mid, mid]
            else:
                c[2], c[3], c[4] = max(c[2], mid), min(c[3], mid), mid
        first_live = min(live) if live else now
        out = [[t, o - b, h - b, l - b, c - b, "gc"] for t, o, h, l, c in bars if t < first_live]
        out += [v + ["spot"] for _, v in sorted(live.items())]
        out = [x for x in out if x[0] >= now - minutes * 60]
        return [[x[0]] + [round(v, 2) for v in x[1:5]] + [x[5]] for x in out]


FEED = Feed()
