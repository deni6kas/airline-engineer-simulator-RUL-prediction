"""Global CSS for the pixel/industrial look."""
from . import config

C = config.COL

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&display=swap');

:root {{
  --bg: {C['bg']}; --panel: {C['panel']}; --panel2: {C['panel_light']};
  --edge: {C['panel_edge']}; --ink: {C['ink']}; --dim: {C['ink_dim']};
  --accent: {C['accent']}; --safe: {C['safe']}; --warn: {C['warning']};
  --crit: {C['critical']}; --gold: {C['gold']};
}}

.stApp {{ background: var(--bg); }}
#MainMenu, header, footer {{ visibility: hidden; }}
.block-container {{ padding: 0.6rem 1.1rem 2rem 1.1rem; max-width: 1400px; }}

/* ---- pixel typography accents ---- */
.pix {{ font-family: 'Press Start 2P', monospace; }}
.mono {{ font-family: 'VT323', monospace; }}

/* ---- HUD ---- */
.hud {{
  display:flex; align-items:center; justify-content:space-between;
  background: linear-gradient(180deg, var(--panel2), var(--panel));
  border:2px solid var(--edge); border-radius:8px;
  padding:8px 16px; margin-bottom:10px;
  box-shadow: 0 0 0 2px #0b1018 inset;
}}
.hud-title {{ font-family:'Press Start 2P'; font-size:15px; color:var(--ink);
  letter-spacing:2px; text-shadow:0 2px 0 #0b1018; }}
.hud-title .star {{ color:var(--gold); }}
.hud-cell {{ display:flex; flex-direction:column; gap:2px; }}
.hud-k {{ font-size:10px; color:var(--dim); text-transform:uppercase; letter-spacing:1px; }}
.hud-v {{ font-family:'VT323'; font-size:22px; color:var(--ink); line-height:1; }}
.hud-budget {{ color:var(--gold); }}
.xpbar {{ width:150px; height:9px; background:#0b1018; border:1px solid var(--edge);
  border-radius:3px; overflow:hidden; }}
.xpbar > span {{ display:block; height:100%; background:linear-gradient(90deg,var(--accent),#7fe3ff); }}

/* ---- panels ---- */
.panel {{ background:var(--panel); border:2px solid var(--edge); border-radius:8px;
  padding:12px 14px; box-shadow:0 0 0 2px #0b1018 inset; }}
.panel h4 {{ margin:0 0 8px 0; font-family:'Press Start 2P'; font-size:11px;
  color:var(--dim); letter-spacing:1px; }}

/* ---- fleet cards ---- */
.fleet-card {{ background:var(--panel2); border:2px solid var(--edge);
  border-radius:7px; padding:8px 10px; margin-bottom:7px; }}
.fleet-card.sel {{ border-color:var(--accent); box-shadow:0 0 8px rgba(54,194,246,.35); }}
.fleet-row {{ display:flex; gap:10px; align-items:center; }}
.fleet-row .thumb {{ width:74px; height:auto; image-rendering:pixelated;
  flex:0 0 auto; filter:drop-shadow(0 2px 3px #0008); }}
.fleet-info {{ flex:1 1 auto; min-width:0; }}
.fleet-top {{ display:flex; justify-content:space-between; align-items:center; }}
.fleet-id {{ font-family:'VT323'; font-size:21px; color:var(--ink); }}
.fleet-sub {{ font-size:10px; color:var(--dim); }}
.fleet-rul {{ font-family:'VT323'; font-size:20px; }}
.dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }}

/* ---- console metrics ---- */
.metric {{ background:var(--panel2); border:2px solid var(--edge); border-radius:7px;
  padding:8px 10px; text-align:center; }}
.metric .k {{ font-size:10px; color:var(--dim); text-transform:uppercase; }}
.metric .v {{ font-family:'VT323'; font-size:34px; line-height:1; color:var(--ink); }}
.metric .v.big {{ font-size:46px; }}

.badge {{ display:inline-block; padding:4px 12px; border-radius:5px;
  font-family:'Press Start 2P'; font-size:10px; letter-spacing:1px; }}
.badge.safe {{ background:rgba(63,208,122,.16); color:var(--safe); border:1px solid var(--safe); }}
.badge.warn {{ background:rgba(245,181,61,.16); color:var(--warn); border:1px solid var(--warn); }}
.badge.crit {{ background:rgba(239,77,77,.16); color:var(--crit); border:1px solid var(--crit); }}

.advice {{ border-left:4px solid var(--warn); background:rgba(245,181,61,.08);
  padding:8px 10px; border-radius:4px; font-size:13px; color:var(--ink); }}
.advice.safe {{ border-color:var(--safe); background:rgba(63,208,122,.08); }}
.advice.crit {{ border-color:var(--crit); background:rgba(239,77,77,.08); }}

/* ---- report modal-card ---- */
.report {{ border:3px solid var(--edge); border-radius:10px; padding:16px 18px;
  margin-bottom:12px; background:linear-gradient(180deg,var(--panel2),var(--panel)); }}
.report.ideal, .report.good {{ border-color:var(--safe); }}
.report.early {{ border-color:var(--warn); }}
.report.crash {{ border-color:var(--crit); }}
.report h3 {{ font-family:'Press Start 2P'; font-size:14px; margin:0 0 8px 0; }}
.report.ideal h3, .report.good h3 {{ color:var(--safe); }}
.report.early h3 {{ color:var(--warn); }}
.report.crash h3 {{ color:var(--crit); }}

/* ---- action buttons ---- */
.stButton > button {{ font-family:'VT323'; font-size:20px; border-radius:7px;
  border:2px solid var(--edge); }}
.stButton > button[kind="primary"] {{ border-color:{C['primary_edge']};
  box-shadow:0 3px 0 {C['primary_edge']}; }}
/* maintenance danger button (anchored) */
div.element-container:has(#maint-anchor) + div.element-container button {{
  background:{C['danger']} !important; color:#fff !important;
  border-color:#7e2f2b !important; box-shadow:0 3px 0 #7e2f2b !important;
}}
div.element-container:has(#flight-anchor) + div.element-container button {{
  font-size:24px !important; padding:10px 0 !important;
}}

/* sensor tiles */
div.element-container:has(.sensor-zone) + div.element-container button {{
  height:70px; font-size:16px; background:var(--panel2);
}}

.legend {{ font-size:11px; color:var(--dim); }}
.legend b.s {{ color:var(--safe); }} .legend b.w {{ color:var(--warn); }} .legend b.c {{ color:var(--crit); }}

.lobby-hero {{ text-align:center; padding:26px 10px 6px; }}
.lobby-hero .t {{ font-family:'Press Start 2P'; font-size:30px; color:var(--ink);
  text-shadow:0 3px 0 #0b1018; }}
.lobby-hero .t .star {{ color:var(--gold); }}
.lobby-hero .s {{ color:var(--dim); font-size:15px; margin-top:10px; }}
.kpi {{ background:var(--panel2); border:2px solid var(--edge); border-radius:8px;
  padding:14px; text-align:center; }}
.kpi .v {{ font-family:'VT323'; font-size:34px; color:var(--ink); }}
.kpi .k {{ font-size:11px; color:var(--dim); text-transform:uppercase; }}
</style>
"""
