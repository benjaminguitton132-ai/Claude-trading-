"""Builds the 10 GUITTON interface mock-ups (static, sample data) into this folder."""
from pathlib import Path

OUT = Path(__file__).resolve().parent
LOGO = "../static/logo-sm.webp"
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800'
         '&family=Cinzel:wght@600;700&family=Playfair+Display:wght@600;700'
         '&family=JetBrains+Mono:wght@400;600&family=Sora:wght@400;600;700&display=swap" rel="stylesheet">')

P = dict(price="3 772,06", chg="+0,42 %", bid="3 771,81", ask="3 772,31", spread="0,50",
         side="BUY", zone="3 777,23 – 3 782,09", sl="3 767,51", tp1="3 791,81", tp2="3 803,96",
         lots="0,03", loss="−45,25 $", gain="+53,16 $", margin="567 $", p1="45 %", p2="27 %", psl="55 %")
AGENTS = [("Horloge", "Fenêtre Londres ouverte", "ok"), ("Contexte", "Tendance baissière · RSI 30,6", "warn"),
          ("Actualités", "9 titres · Fed, inflation", "warn"), ("Macro", "Dollar +0,26 % · taux −0,02", "warn"),
          ("Entrée", "Cassure haussière 09:30", "ok"), ("Sortie", "SL · TP1 · TP2 posés", "ok"),
          ("Time Machine", "TP1 45 % · TP2 27 %", "ok"), ("Budget", "0,03 lot · marge 567 $", "ok"),
          ("Risque", "PASS", "ok"), ("Ticket", "BUY 0,03 @ 3 779,66", "ok"), ("Alertes", "Suivi prêt", "ok")]
LINKS = ["Analyse", "Trade en cours", "Historique", "Réglages"]


def nav(cls="nav", links=True, price=True, extra=""):
    l = "".join('<a class="%s">%s</a>' % ("on" if i == 0 else "", x) for i, x in enumerate(LINKS)) if links else ""
    pr = ('<div class="navpx"><span class="dot"></span>XAU/USD <b>%s</b> <em>%s</em></div>' % (P["price"], P["chg"])) if price else ""
    return '<header class="%s"><img class="logo" src="%s" alt="GUITTON"><nav>%s</nav>%s%s</header>' % (cls, LOGO, l, pr, extra)


def params(cls="params"):
    return ('<div class="%s"><label>Capital<input value="5 000 $"></label><label>Risque / trade<input value="1 %%"></label>'
            '<label>Levier broker<input value="1:20"></label></div>' % cls)


def button(text="Lancer une analyse", cls="cta"):
    return '<button class="%s">%s</button>' % (cls, text)


def levels(cls="levels"):
    rows = [("Fourchette d'entrée", P["zone"], "z"), ("Stop loss", P["sl"], "r"), ("TP1 · 50 %", P["tp1"], "g"),
            ("TP2", P["tp2"], "g"), ("Lots", P["lots"], ""), ("Perte max", P["loss"], "r"), ("Gain du plan", P["gain"], "g"),
            ("Marge", P["margin"], "")]
    return '<div class="%s">%s</div>' % (cls, "".join('<div class="lv %s"><small>%s</small><b>%s</b></div>' % (c, a, b) for a, b, c in rows))


def odds(cls="odds"):
    return ('<div class="%s"><div class="bar"><i style="width:45%%" class="g"></i><i style="width:55%%" class="r"></i></div>'
            '<div class="ol"><span>TP1 avant SL <b>%s</b></span><span>TP2 <b>%s</b></span><span>SL avant TP1 <b>%s</b></span></div></div>'
            % (cls, P["p1"], P["p2"], P["psl"]))


def agents(cls="agents"):
    return '<div class="%s">%s</div>' % (cls, "".join(
        '<div class="ag %s"><i></i><b>%s</b><span>%s</span></div>' % (s, n, t) for n, t, s in AGENTS))


def ticket(cls="ticket"):
    return '<div class="%s">BUY XAUUSD 0.03 lot @ 3779.66 · SL 3767.51 · TP1 3791.81 (50 %%) · TP2 3803.96</div>' % cls


def chart(cls="chart", color="#e7b84a", grid="rgba(255,255,255,.06)"):
    import random
    rnd = random.Random(7)
    v, pts = 50, []
    for i in range(60):
        v += rnd.uniform(-3, 3.4)
        pts.append((i * 10, 100 - v))
    path = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", x, y) for i, (x, y) in enumerate(pts))
    g = "".join('<line x1="0" x2="600" y1="%d" y2="%d" stroke="%s"/>' % (y, y, grid) for y in (20, 45, 70, 95))
    return ('<svg class="%s" viewBox="0 0 600 120" preserveAspectRatio="none">%s'
            '<path d="%s L590,120 L0,120 Z" fill="%s" opacity=".12"/><path d="%s" fill="none" stroke="%s" stroke-width="2"/>'
            '<line x1="0" x2="600" y1="38" y2="38" stroke="#2bd47d" stroke-dasharray="5 4"/>'
            '<line x1="0" x2="600" y1="88" y2="88" stroke="#ff5a5a" stroke-dasharray="5 4"/></svg>'
            % (cls, g, path, color, path, color))


def instr(cls="instr"):
    return ('<div class="%s"><div class="ic">★</div><div><b>CLÔTUREZ TP1</b><span>TP1 atteint : ferme 50 %% (0,015 lot)</span></div>'
            '<button>C\'est fait</button></div>' % cls)


def page(title, css, body):
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title>%s<style>*{box-sizing:border-box}body{margin:0}input{font:inherit}button{font:inherit;cursor:pointer}'
            'label{display:block}label input{display:block;width:100%%}%s</style></head><body>%s</body></html>' % (title, FONTS, css, body))


BASE_LV = (".lv small{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;opacity:.6}"
           ".lv b{font-size:20px;font-variant-numeric:tabular-nums}.lv.r b{color:#ff5a5a}.lv.g b{color:#2bd47d}"
           ".bar{display:flex;height:8px;border-radius:9px;overflow:hidden}.bar i{display:block}.bar .g{background:#2bd47d}.bar .r{background:#ff5a5a}"
           ".ol{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;margin-top:8px;opacity:.85}"
           ".ag{display:grid;grid-template-columns:14px 110px 1fr;gap:8px;align-items:center;font-size:13px;padding:6px 0}"
           ".ag i{width:9px;height:9px;border-radius:50%;background:#2bd47d}.ag.warn i{background:#f0a63a}.ag span{opacity:.6}"
           ".navpx{display:flex;align-items:center;gap:8px;font-size:13px;white-space:nowrap}.navpx em{font-style:normal;color:#2bd47d}"
           ".dot{width:8px;height:8px;border-radius:50%;background:#2bd47d;box-shadow:0 0 8px #2bd47d}")

D = []

# 1 ------------------------------------------------------------------ Noir & Or
D.append(("Noir & Or", "Sobre et premium : fond noir, filets dorés, deux colonnes.", page("1", BASE_LV + """
body{background:#070707;color:#eee;font-family:Inter}
.nav{display:flex;align-items:center;gap:28px;padding:12px 40px;border-bottom:1px solid #2a2310;background:#0b0b0b}
.logo{height:52px}nav{display:flex;gap:22px;flex:1}nav a{color:#999;font-size:14px}nav a.on{color:#e7b84a}
main{max-width:1180px;margin:0 auto;padding:36px 40px;display:grid;grid-template-columns:360px 1fr;gap:28px}
.card{background:#0f0f0f;border:1px solid #221d10;border-radius:16px;padding:22px}
h1{font:600 13px Inter;letter-spacing:.2em;color:#e7b84a;margin:0 0 6px}.big{font:700 44px Inter;color:#fff}
.params label{font-size:12px;color:#888;margin-top:12px}.params input{background:#000;border:1px solid #2a2a2a;color:#fff;padding:11px;border-radius:10px;margin-top:5px}
.cta{width:100%;margin-top:18px;padding:16px;border:0;border-radius:12px;background:linear-gradient(#f3d27c,#c8952f);font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.levels{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#221d10;border-radius:12px;overflow:hidden;margin:16px 0}
.lv{background:#0f0f0f;padding:14px}.lv.z{grid-column:span 2}.lv.z b{color:#e7b84a}
.side{font:700 30px Cinzel;color:#2bd47d}.ticket{font:12px 'JetBrains Mono';color:#d9c48f;border:1px dashed #333;padding:10px;border-radius:10px;margin-top:14px}
""", nav() + '<main><div><div class="card"><h1>XAUUSD SPOT</h1><div class="big">%s</div><div style="color:#888;font-size:13px">bid %s · ask %s</div>%s%s</div>'
       '<div class="card" style="margin-top:20px">%s</div></div><div class="card"><div class="side">BUY · Trade proposé</div>%s%s%s</div></main>'
       % (P["price"], P["bid"], P["ask"], params(), button(), agents(), levels(), odds(), ticket()))))

# 2 ------------------------------------------------------------------ Midnight Blue
D.append(("Bleu nuit", "Reprend les bleus du logo : dégradé marine, cartes en verre, accents cyan.", page("2", BASE_LV + """
body{background:radial-gradient(1200px 600px at 70% -10%,#123a6b,#050c1c 60%);color:#e8f0ff;font-family:Sora;min-height:100vh}
.nav{display:flex;align-items:center;gap:30px;padding:14px 48px;background:rgba(5,12,28,.7);backdrop-filter:blur(10px);border-bottom:1px solid rgba(80,160,255,.15)}
.logo{height:50px;border-radius:10px}nav{display:flex;gap:6px;flex:1}nav a{padding:8px 14px;border-radius:99px;font-size:14px;color:#9fb6d9}nav a.on{background:rgba(64,156,255,.18);color:#fff}
.hero{max-width:1180px;margin:0 auto;padding:44px 48px 10px;display:flex;align-items:flex-end;justify-content:space-between}
.hero h1{font:700 52px Sora;margin:0}.hero p{color:#8fb0dd;margin:4px 0 0}
main{max-width:1180px;margin:0 auto;padding:20px 48px;display:grid;grid-template-columns:1fr 1.4fr;gap:22px}
.glass{background:rgba(20,45,90,.35);border:1px solid rgba(110,180,255,.18);border-radius:20px;padding:22px;backdrop-filter:blur(12px)}
.params{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.params label{font-size:12px;color:#8fb0dd}.params input{margin-top:5px;padding:11px;border-radius:12px;border:1px solid rgba(110,180,255,.25);background:rgba(0,0,0,.25);color:#fff}
.cta{margin-top:16px;width:100%;padding:16px;border:0;border-radius:14px;background:linear-gradient(90deg,#3aa0ff,#2bd4c8);color:#02101f;font-weight:700}
.levels{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}.lv{background:rgba(0,0,0,.25);border-radius:14px;padding:12px}.lv.z{grid-column:span 2}.lv.z b{color:#ffd36a}
.chart{width:100%;height:120px;margin-top:6px}
""", nav() + '<div class="hero"><div><p>XAUUSD · or spot en temps réel</p><h1>%s</h1></div><div style="color:#2bd47d">%s aujourd\'hui</div></div>'
       '<main><div class="glass">%s%s<div style="margin-top:18px">%s</div></div><div class="glass"><b style="font-size:22px;color:#2bd47d">BUY XAUUSD</b>%s%s%s</div></main>'
       % (P["price"], P["chg"], params(), button(), agents(), chart(color="#3aa0ff"), levels(), odds()))))

# 3 ------------------------------------------------------------------ Terminal Pro
D.append(("Terminal Pro", "Façon terminal de trading : dense, monospace, ambre sur noir.", page("3", BASE_LV + """
body{background:#000;color:#ffb000;font-family:'JetBrains Mono';font-size:13px}
.nav{display:flex;align-items:center;gap:20px;padding:6px 16px;border-bottom:1px solid #332300;background:#0a0700}
.logo{height:38px}nav{display:flex;gap:2px;flex:1}nav a{padding:6px 12px;border:1px solid #332300;color:#a87400}nav a.on{background:#ffb000;color:#000}
.navpx b{color:#fff}
main{display:grid;grid-template-columns:300px 1fr 320px;gap:1px;background:#332300;height:calc(100vh - 51px)}
section{background:#000;padding:14px}h2{font-size:11px;letter-spacing:.2em;color:#664600;margin:0 0 10px;border-bottom:1px solid #221700;padding-bottom:6px}
.params label{color:#a87400;margin-bottom:8px}.params input{background:#0a0700;border:1px solid #332300;color:#fff;padding:7px}
.cta{width:100%;padding:12px;background:#ffb000;color:#000;border:0;font-weight:700}
.levels{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#221700}.lv{background:#000;padding:10px}.lv b{font-size:18px;color:#fff}.lv.z b{color:#ffb000}
.chart{width:100%;height:220px}.ticket{margin-top:12px;color:#fff;border:1px solid #332300;padding:8px}
.ag{grid-template-columns:12px 100px 1fr}.ag span{color:#a87400;opacity:1}
""", nav() + '<main><section><h2>PARAMÈTRES</h2>%s%s<h2 style="margin-top:20px">AGENTS</h2>%s</section>'
       '<section><h2>XAUUSD · 1M · SPOT %s</h2>%s<h2 style="margin-top:14px">PROPOSITION · BUY</h2>%s%s</section>'
       '<section><h2>NIVEAUX</h2>%s</section></main>'
       % (params(), button("[ LANCER ANALYSE ]"), agents(), P["price"], chart(color="#ffb000", grid="#1a1200"), odds(), ticket(), levels()))))

# 4 ------------------------------------------------------------------ Clean Light
D.append(("Clair épuré", "Site fintech lumineux : fond blanc, beaucoup d'air, touches dorées.", page("4", BASE_LV + """
body{background:#f6f5f1;color:#17150f;font-family:Inter}
.nav{display:flex;align-items:center;gap:32px;padding:14px 56px;background:#fff;box-shadow:0 1px 0 #ebe7dc}
.logo{height:46px;border-radius:8px}nav{display:flex;gap:26px;flex:1}nav a{font-size:14px;color:#7b7464}nav a.on{color:#17150f;font-weight:600}
.hero{max-width:1100px;margin:0 auto;padding:48px 56px 24px;text-align:center}.hero h1{font:800 56px Inter;margin:6px 0;letter-spacing:-.02em}
.hero p{color:#8b8473;margin:0}.params{display:flex;gap:12px;justify-content:center;margin-top:24px}.params label{font-size:12px;color:#8b8473;text-align:left}
.params input{margin-top:5px;width:150px;padding:12px;border-radius:12px;border:1px solid #e3ded1;background:#fff}
.cta{margin:18px auto 0;display:block;padding:16px 40px;border:0;border-radius:99px;background:#17150f;color:#f3d27c;font-weight:700}
main{max-width:1100px;margin:0 auto;padding:10px 56px 40px;display:grid;grid-template-columns:1.5fr 1fr;gap:20px}
.card{background:#fff;border-radius:20px;padding:24px;box-shadow:0 10px 30px rgba(60,50,20,.06)}
.levels{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:16px 0}.lv.z{grid-column:span 2}.lv.z b{color:#b8862b}.lv.g b{color:#11804a}.lv.r b{color:#c0392b}
.ag i{background:#11804a}.ag.warn i{background:#d08a1a}.navpx em{color:#11804a}
""", nav() + '<div class="hero"><p>XAUUSD · or spot</p><h1>%s</h1><p style="color:#11804a">%s</p>%s%s</div>'
       '<main><div class="card"><b style="font-size:22px;color:#11804a">BUY · Trade proposé</b>%s%s</div><div class="card">%s</div></main>'
       % (P["price"], P["chg"], params(), button(), levels(), odds(), agents()))))

# 5 ------------------------------------------------------------------ Glass on logo
D.append(("Verre dépoli", "Le logo en grand fond flouté, cartes en verre par-dessus.", page("5", BASE_LV + """
body{font-family:Inter;color:#fff;min-height:100vh;background:#030814}
.bgimg{position:fixed;inset:-40px;background:url(../static/logo.webp) center/cover;filter:blur(28px) brightness(.45);z-index:-1}
.nav{display:flex;align-items:center;gap:28px;margin:18px auto 0;max-width:1180px;padding:10px 18px;border-radius:18px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);backdrop-filter:blur(16px)}
.logo{height:48px;border-radius:10px}nav{display:flex;gap:20px;flex:1}nav a{font-size:14px;color:#c9d3e6}nav a.on{color:#ffd36a}
main{max-width:1180px;margin:28px auto;display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;padding:0 0 40px}
.gl{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);border-radius:22px;padding:22px;backdrop-filter:blur(18px)}
.span2{grid-column:span 2}.big{font:800 48px Inter}.params label{font-size:12px;color:#c9d3e6;margin-top:10px}
.params input{margin-top:5px;padding:11px;border-radius:12px;border:1px solid rgba(255,255,255,.2);background:rgba(0,0,0,.25);color:#fff}
.cta{margin-top:16px;width:100%;padding:15px;border:0;border-radius:14px;background:#ffd36a;color:#1b1200;font-weight:700}
.levels{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}.lv{background:rgba(0,0,0,.25);border-radius:14px;padding:12px}.lv.z{grid-column:span 2}.lv.z b{color:#ffd36a}
""", '<div class="bgimg"></div>' + nav() + '<main><div class="gl"><div style="color:#c9d3e6">XAUUSD spot</div><div class="big">%s</div>%s%s</div>'
       '<div class="gl span2"><b style="font-size:24px;color:#2bd47d">BUY XAUUSD</b>%s%s</div><div class="gl span2">%s</div><div class="gl">%s</div></main>'
       % (P["price"], params(), button(), levels(), odds(), chart(color="#ffd36a"), agents()))))

# 6 ------------------------------------------------------------------ Sidebar dashboard
D.append(("Tableau de bord", "Menu latéral comme un vrai logiciel, logo en haut du menu.", page("6", BASE_LV + """
body{font-family:Inter;background:#0b0d10;color:#e8e8e8;display:grid;grid-template-columns:250px 1fr;min-height:100vh}
aside{background:#07080a;border-right:1px solid #1b1e23;padding:18px}aside .logo{width:100%;border-radius:12px}
aside a{display:block;padding:11px 14px;border-radius:10px;color:#8d939c;margin-top:4px;font-size:14px}aside a.on{background:#16191e;color:#f3d27c}
.top{display:flex;justify-content:space-between;align-items:center;padding:18px 28px;border-bottom:1px solid #1b1e23}
.top h1{font:700 20px Inter;margin:0}
.grid{padding:24px 28px;display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.k{background:#111419;border:1px solid #1b1e23;border-radius:14px;padding:16px}.k>small{color:#8d939c;font-size:12px}.k>b{display:block;font-size:24px;margin-top:4px}.k .lv b{font-size:17px}.k .odds b{font-size:13px}
.w2{grid-column:span 2}.w3{grid-column:span 3}.w4{grid-column:span 4}
.params{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.params label{font-size:12px;color:#8d939c}.params input{margin-top:5px;padding:10px;border-radius:10px;border:1px solid #23272e;background:#0b0d10;color:#fff}
.cta{margin-top:14px;padding:13px 22px;border:0;border-radius:10px;background:#f3d27c;color:#1b1200;font-weight:700}
.levels{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:10px}.lv.z{grid-column:span 2}.lv.z b{color:#f3d27c}.chart{width:100%;height:150px}
""", '<aside><img class="logo" src="%s"><div style="margin-top:18px">%s</div></aside>' % (LOGO, "".join('<a class="%s">%s</a>' % ("on" if i == 0 else "", x) for i, x in enumerate(LINKS)))
       + '<div><div class="top"><h1>Analyse XAUUSD</h1><div class="navpx"><span class="dot"></span>XAU/USD <b>%s</b> <em>%s</em></div></div><div class="grid">'
       '<div class="k"><small>Prix spot</small><b>%s</b></div><div class="k"><small>Spread</small><b>%s</b></div><div class="k"><small>Session</small><b>Londres</b></div><div class="k"><small>Risque</small><b>50 $</b></div>'
       '<div class="k w2">%s%s</div><div class="k w2"><b style="color:#2bd47d">BUY · Trade proposé</b>%s</div><div class="k w3">%s%s</div><div class="k">%s</div></div></div>'
       % (P["price"], P["chg"], P["price"], P["spread"], params(), button(), levels(), chart(color="#f3d27c"), odds(), agents()))))

# 7 ------------------------------------------------------------------ Luxury serif
D.append(("Luxe éditorial", "Typographie serif, filets or fins, mise en page de magazine.", page("7", BASE_LV + """
body{background:#0a0908;color:#efe7d6;font-family:Inter}
.nav{display:flex;flex-direction:column;align-items:center;gap:12px;padding:20px 0 12px;border-bottom:1px solid #3a2f17}
.logo{height:64px;border-radius:12px}nav{display:flex;gap:40px}nav a{font:600 12px Inter;letter-spacing:.25em;text-transform:uppercase;color:#9c8f73}nav a.on{color:#e7c27a}.navpx{display:none}
.hero{text-align:center;padding:40px 0 20px}.hero small{letter-spacing:.35em;color:#9c8f73;font-size:11px}.hero h1{font:700 64px 'Playfair Display';margin:8px 0;color:#f6e7c1}
.rule{width:120px;height:1px;background:#e7c27a;margin:0 auto}
main{max-width:1000px;margin:0 auto;padding:20px 40px 50px}
.params{display:flex;gap:30px;justify-content:center}.params label{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#9c8f73}.params input{margin-top:6px;width:170px;background:transparent;border:0;border-bottom:1px solid #5a4a26;color:#fff;padding:8px 0;font-size:18px}
.cta{display:block;margin:26px auto;padding:15px 46px;background:transparent;border:1px solid #e7c27a;color:#e7c27a;letter-spacing:.3em;text-transform:uppercase;font-size:12px}
h2{font:700 30px 'Playfair Display';text-align:center;color:#2bd47d;margin:30px 0 4px}
.levels{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #3a2f17;border-bottom:1px solid #3a2f17;margin:20px 0}.lv{padding:18px;border-right:1px solid #2a2212;text-align:center}.lv.z b{color:#e7c27a}
.lv b{font-family:'Playfair Display';font-size:22px}
""", nav() + '<div class="hero"><small>XAUUSD · OR SPOT</small><h1>%s</h1><div class="rule"></div></div><main>%s%s<h2>Achat proposé</h2>%s%s</main>'
       % (P["price"], params(), button(), levels(), odds()))))

# 8 ------------------------------------------------------------------ Neon
D.append(("Néon trading", "Sombre avec halos vert/rouge/cyan, très « salle de marché ».", page("8", BASE_LV + """
body{background:#03060a;color:#dff;font-family:Sora}
.nav{display:flex;align-items:center;gap:26px;padding:12px 40px;border-bottom:1px solid #0c2a33;box-shadow:0 0 40px rgba(0,220,255,.08)}
.logo{height:50px;border-radius:10px;box-shadow:0 0 22px rgba(255,200,80,.35)}nav{display:flex;gap:22px;flex:1}nav a{color:#6fa3ad;font-size:14px}nav a.on{color:#4ff;text-shadow:0 0 10px #4ff}
main{max-width:1200px;margin:0 auto;padding:30px 40px;display:grid;grid-template-columns:1.6fr 1fr;gap:22px}
.n{border:1px solid #0e3540;border-radius:18px;padding:22px;background:linear-gradient(180deg,#061219,#03080c);box-shadow:inset 0 0 30px rgba(0,220,255,.04)}
.big{font:700 50px Sora;color:#4f8;text-shadow:0 0 18px rgba(68,255,136,.5)}.chart{width:100%;height:170px;filter:drop-shadow(0 0 6px #4ff)}
.params{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.params label{font-size:12px;color:#6fa3ad}.params input{margin-top:5px;padding:11px;border-radius:12px;border:1px solid #0e3540;background:#020507;color:#fff}
.cta{margin-top:14px;width:100%;padding:15px;border:1px solid #4ff;border-radius:14px;background:rgba(0,255,255,.08);color:#4ff;font-weight:700;letter-spacing:.12em;box-shadow:0 0 20px rgba(0,255,255,.25)}
.levels{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.lv{border:1px solid #0e3540;border-radius:12px;padding:12px}.lv.z{grid-column:span 2}.lv.z b{color:#ffd36a;text-shadow:0 0 12px rgba(255,211,106,.5)}
.lv.g b{text-shadow:0 0 10px rgba(43,212,125,.6)}.lv.r b{text-shadow:0 0 10px rgba(255,90,90,.6)}
""", nav() + '<main><div class="n"><div style="color:#6fa3ad">XAUUSD · temps réel</div><div class="big">%s</div>%s%s%s</div>'
       '<div class="n"><b style="font-size:24px;color:#4f8;text-shadow:0 0 12px #4f8">▲ BUY</b>%s%s</div></main>'
       % (P["price"], chart(color="#44ffee", grid="#0a1f26"), params(), button(), levels(), odds()))))

# 9 ------------------------------------------------------------------ App mobile-first
D.append(("Appli mobile", "Colonne centrée, grosses cartes arrondies, barre d'onglets en bas : idéal téléphone.", page("9", BASE_LV + """
body{background:#0c0c0e;color:#f2f2f2;font-family:Inter;padding-bottom:90px}
.nav{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;max-width:520px;margin:0 auto}.logo{height:44px;border-radius:10px}nav{display:none}
.wrap{max-width:520px;margin:0 auto;padding:0 18px}
.c{background:#17171a;border-radius:24px;padding:20px;margin-top:14px}.big{font:800 46px Inter}
.params{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}.params label{font-size:11px;color:#8a8a90}.params input{margin-top:5px;padding:11px;border-radius:14px;border:0;background:#222226;color:#fff}
.cta{margin-top:14px;width:100%;padding:18px;border:0;border-radius:18px;background:linear-gradient(#f3d27c,#c8952f);font-weight:800;color:#1b1200;font-size:16px}
.levels{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.lv{background:#222226;border-radius:16px;padding:12px}.lv.z{grid-column:span 2}.lv.z b{color:#f3d27c}
.tab{position:fixed;left:0;right:0;bottom:0;display:flex;justify-content:space-around;padding:12px 0 22px;background:#111113;border-top:1px solid #222}.tab a{font-size:11px;color:#8a8a90;text-align:center}.tab a.on{color:#f3d27c}
.tab a i{display:block;font-style:normal;font-size:20px}
""", nav() + '<div class="wrap"><div class="c"><div style="color:#8a8a90">XAUUSD spot</div><div class="big">%s</div><div style="color:#2bd47d">%s</div></div>'
       '<div class="c">%s%s</div><div class="c"><b style="font-size:22px;color:#2bd47d">BUY · Trade proposé</b>%s%s</div></div>'
       '<div class="tab"><a class="on"><i>◎</i>Analyse</a><a><i>📈</i>Trade</a><a><i>☰</i>Historique</a><a><i>⚙</i>Réglages</a></div>'
       % (P["price"], P["chg"], params(), button(), levels(), odds()))))

# 10 ----------------------------------------------------------------- Stepper landing
D.append(("Parcours guidé", "Site en 3 étapes numérotées : Paramètres → Analyse → Trade en direct.", page("10", BASE_LV + """
body{background:#09090b;color:#eee;font-family:Inter}
.nav{display:flex;align-items:center;gap:30px;padding:14px 48px;border-bottom:1px solid #1d1d22}.logo{height:48px;border-radius:9px}
nav{display:flex;gap:24px;flex:1}nav a{font-size:14px;color:#8a8a92}nav a.on{color:#f3d27c}
.steps{max-width:1100px;margin:30px auto 0;display:flex;gap:12px;padding:0 48px}.st{flex:1;display:flex;align-items:center;gap:10px;padding:12px 16px;border-radius:12px;background:#121216;color:#8a8a92;font-size:14px}
.st b{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:#1d1d22;color:#ddd}.st.on{background:#1c1708;color:#f3d27c}.st.on b{background:#f3d27c;color:#1b1200}.st.done b{background:#2bd47d;color:#02170c}
main{max-width:1100px;margin:20px auto;padding:0 48px 40px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
.c{background:#121216;border:1px solid #1d1d22;border-radius:18px;padding:22px}h3{margin:0 0 12px;font-size:15px;color:#aaa;font-weight:600}
.params{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.params label{font-size:12px;color:#8a8a92}.params input{margin-top:5px;padding:11px;border-radius:10px;border:1px solid #26262c;background:#09090b;color:#fff}
.cta{margin-top:14px;width:100%;padding:15px;border:0;border-radius:12px;background:#f3d27c;color:#1b1200;font-weight:700}
.levels{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:6px}.lv.z{grid-column:span 2}.lv.z b{color:#f3d27c}
.instr{display:flex;gap:12px;align-items:center;border:1px solid #f3d27c;border-radius:14px;padding:12px;margin-top:12px}.instr .ic{width:40px;height:40px;border-radius:50%;border:2px solid #fff;display:grid;place-items:center}
.instr b{display:block}.instr span{color:#aaa;font-size:13px}.instr button{margin-left:auto;border:0;border-radius:9px;padding:9px 12px;background:#f3d27c}.chart{width:100%;height:110px}
""", nav() + '<div class="steps"><div class="st done"><b>✓</b>Paramètres</div><div class="st on"><b>2</b>Analyse des 11 agents</div><div class="st"><b>3</b>Trade en direct</div></div>'
       '<main><div class="c"><h3>1 · Tes paramètres</h3>%s%s<h3 style="margin-top:22px">Les 11 agents</h3>%s</div>'
       '<div class="c"><h3>2 · Trade proposé</h3><b style="font-size:24px;color:#2bd47d">BUY XAUUSD</b>%s%s<h3 style="margin-top:22px">3 · Aperçu du suivi en direct</h3>%s%s</div></main>'
       % (params(), button(), agents(), levels(), odds(), chart(color="#f3d27c"), instr()))))


if __name__ == "__main__":
    for i, (name, desc, html) in enumerate(D, 1):
        (OUT / ("%02d.html" % i)).write_text(html)
    print("\n".join("%02d %s — %s" % (i, n, d) for i, (n, d, _) in enumerate(D, 1)))
