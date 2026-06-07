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
.stApp, .stApp * {{
  animation: none !important;
  transition: none !important;
}}
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
  padding:8px 10px; text-align:center; min-height:114px;
  display:flex; flex-direction:column; justify-content:center; }}
.metric .k {{ font-size:10px; color:var(--dim); text-transform:uppercase; }}
.metric .v {{ font-family:'VT323'; font-size:34px; line-height:1; color:var(--ink); }}
.metric .v.big {{ font-size:46px; }}
.metric.locked {{ opacity:.9; border-color:var(--warn); }}
.metric.locked .v {{ color:var(--warn); font-size:30px; }}

.badge {{ display:inline-block; padding:4px 12px; border-radius:5px;
  font-family:'Press Start 2P'; font-size:10px; letter-spacing:1px; }}
.badge.safe {{ background:rgba(63,208,122,.16); color:var(--safe); border:1px solid var(--safe); }}
.badge.warn {{ background:rgba(245,181,61,.16); color:var(--warn); border:1px solid var(--warn); }}
.badge.crit {{ background:rgba(239,77,77,.16); color:var(--crit); border:1px solid var(--crit); }}
.badge.locked-badge {{ background:rgba(245,181,61,.12); color:var(--warn); border:1px solid var(--warn); }}

.advice {{ border-left:4px solid var(--warn); background:rgba(245,181,61,.08);
  padding:8px 10px; border-radius:4px; font-size:13px; color:var(--ink); }}
.advice.safe {{ border-color:var(--safe); background:rgba(63,208,122,.08); }}
.advice.crit {{ border-color:var(--crit); background:rgba(239,77,77,.08); }}
.locked-advice {{ border-color:var(--warn); background:rgba(245,181,61,.07); color:var(--dim); }}

.departure-card {{
  display:flex; justify-content:space-between; align-items:center; gap:12px;
  margin:0 0 10px 0; padding:10px 12px; border:2px solid var(--edge);
  border-radius:8px; background:rgba(13,20,32,.65);
  color:var(--ink); font-size:13px;
}}
.departure-card b {{ font-family:'Press Start 2P'; font-size:9px; color:var(--dim); }}
.departure-card span {{ color:var(--gold); }}
.departure-card .timer {{
  font-family:'Press Start 2P'; font-size:18px; min-width:82px; text-align:center;
  padding:7px 9px; border-radius:6px; background:#0b1018; border:1px solid var(--edge);
}}
.departure-card.ok .timer {{ color:var(--safe); }}
.departure-card.warn .timer {{ color:var(--warn); }}
.departure-card.danger .timer {{ color:var(--crit); }}
.departure-card.paused .timer {{ color:var(--dim); }}
.departure-card.muted {{ color:var(--dim); }}

/* ---- required report overlay ---- */
.report-overlay {{
  position:fixed; inset:0; z-index:9990;
  background:rgba(4, 8, 14, .74);
  backdrop-filter: blur(2px);
  display:flex; align-items:center; justify-content:center;
  padding:24px;
}}
.report {{
  border:3px solid var(--edge); border-radius:10px; padding:18px 20px;
  background:linear-gradient(180deg,var(--panel2),var(--panel));
  box-shadow:0 20px 70px rgba(0,0,0,.65), 0 0 0 2px #0b1018 inset;
}}
.report-modal {{
  width:min(860px, calc(100vw - 56px));
  max-height:calc(100vh - 160px);
  overflow:auto;
}}
.report.ideal, .report.good {{ border-color:var(--safe); }}
.report.early {{ border-color:var(--warn); }}
.report.crash {{ border-color:var(--crit); }}
.report.telemetry_end {{ border-color:var(--crit); }}
.report.bankrupt {{ border-color:var(--crit); }}
.report h3 {{ font-family:'Press Start 2P'; font-size:14px; margin:0 0 8px 0; }}
.report.ideal h3, .report.good h3 {{ color:var(--safe); }}
.report.early h3 {{ color:var(--warn); }}
.report.crash h3, .report.telemetry_end h3, .report.bankrupt h3 {{ color:var(--crit); }}
.report-required {{
  margin-top:12px; padding-top:10px; border-top:1px solid var(--edge);
  color:var(--dim); font-size:12px;
}}
div.element-container:has(#report-ok-anchor) + div.element-container {{
  position:fixed; z-index:10000; left:calc(50% - 260px); bottom:calc(50% - 205px);
  width:240px !important;
}}
div.element-container:has(#report-summary-anchor) + div.element-container {{
  position:fixed; z-index:10000; left:calc(50% + 20px); bottom:calc(50% - 205px);
  width:240px !important;
}}
div.element-container:has(#report-ok-anchor) + div.element-container button,
div.element-container:has(#report-summary-anchor) + div.element-container button {{
  min-height:54px !important;
}}

.fleet-wait-overlay {{
  position:fixed; inset:0; z-index:10800;
  background:rgba(4, 8, 14, .78);
  backdrop-filter:blur(2px);
  display:flex; align-items:center; justify-content:center;
  padding:24px;
}}
.fleet-wait-card {{
  width:min(820px, calc(100vw - 48px));
  border:3px solid var(--warn);
  border-radius:12px;
  background:linear-gradient(180deg,var(--panel2),var(--panel));
  color:var(--ink);
  padding:26px 30px;
  box-shadow:0 22px 80px rgba(0,0,0,.7), 0 0 0 2px #0b1018 inset;
  text-align:center;
}}
.fleet-wait-card h3 {{
  margin:0 0 14px 0;
  font-family:'Press Start 2P';
  font-size:15px;
  color:var(--warn);
}}
.fleet-wait-card p {{
  margin:0 auto 18px auto;
  max-width:720px;
  font-size:22px;
  line-height:1.45;
}}
.fleet-wait-timer {{
  display:inline-block;
  min-width:140px;
  padding:12px 18px;
  border:2px solid var(--edge);
  border-radius:8px;
  background:#0b1018;
  color:var(--gold);
  font-family:'Press Start 2P';
  font-size:24px;
}}
.fleet-wait-sub {{
  margin-top:14px;
  color:var(--dim);
  font-size:13px;
}}

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
  min-height:76px !important;
}}
div.element-container:has(#maint-anchor) + div.element-container button {{
  min-height:76px !important;
}}
div.element-container:has(#summary-anchor) + div.element-container button {{
  min-height:58px !important;
}}

/* sensor tiles */
div.element-container:has(.sensor-zone) + div.element-container button {{
  height:70px; font-size:18px; background:var(--panel2);
}}

.console-bottom {{
  margin-top:10px; padding-top:10px; border-top:1px solid var(--edge);
}}

.legend {{ font-size:11px; color:var(--dim); }}
.legend b.s {{ color:var(--safe); }} .legend b.w {{ color:var(--warn); }} .legend b.c {{ color:var(--crit); }}

.lobby-hero {{ text-align:center; padding:26px 10px 6px; }}
.lobby-hero .t {{ font-family:'Press Start 2P'; font-size:30px; color:var(--ink);
  text-shadow:0 3px 0 #0b1018; }}
.lobby-hero .t .star {{ color:var(--gold); }}
.lobby-hero .s {{ color:var(--dim); font-size:15px; margin-top:10px; }}
.tutorial-card {{
  margin-top:10px;
}}
.tutorial-card p {{
  color:var(--ink);
  font-size:14px;
  line-height:1.65;
}}
.kpi {{ background:var(--panel2); border:2px solid var(--edge); border-radius:8px;
  padding:14px; text-align:center; }}
.kpi .v {{ font-family:'VT323'; font-size:34px; color:var(--ink); }}
.kpi .k {{ font-size:11px; color:var(--dim); text-transform:uppercase; }}

.notice-overlay {{
  position:fixed;
  inset:0;
  z-index:11000;
  background:rgba(4, 8, 14, .56);
  display:flex;
  align-items:center;
  justify-content:center;
  padding:24px;
}}
.notice-toast {{
  width:min(680px, calc(100vw - 48px));
  min-height:150px;
  padding:28px 32px 86px 32px;
  border:2px solid var(--warn);
  border-radius:10px;
  background:linear-gradient(180deg,var(--panel2),var(--panel));
  color:var(--ink);
  font-size:25px;
  line-height:1.45;
  box-shadow:0 18px 50px rgba(0,0,0,.55), 0 0 0 2px #0b1018 inset;
}}
.notice-toast b {{
  color:var(--warn);
  font-family:'Press Start 2P';
  font-size:18px;
}}
div.element-container:has(#notice-ok-anchor) + div.element-container {{
  position:fixed;
  z-index:11001;
  left:50%;
  transform:translateX(-50%);
  bottom:calc(50% - 132px);
  width:180px !important;
}}

/* ---- responsive mobile/tablet layout ---- */
[data-testid="stImage"] img,
iframe[title*="streamlit_image_coordinates"] {{
  max-width:100% !important;
}}

@media (max-width: 900px) {{
  .block-container {{
    padding:0.45rem 0.55rem 1.2rem 0.55rem;
    max-width:100vw;
  }}

  [data-testid="stHorizontalBlock"] {{
    flex-wrap:wrap !important;
    gap:0.85rem !important;
  }}
  [data-testid="stHorizontalBlock"] > div {{
    min-width:100% !important;
    flex:1 1 100% !important;
  }}

  .hud {{
    flex-wrap:wrap;
    gap:8px;
    padding:8px 10px;
  }}
  .hud-title {{
    order:-1;
    width:100%;
    text-align:center;
    font-size:12px;
    letter-spacing:1px;
  }}
  .hud > div:last-child {{
    width:100%;
    display:grid !important;
    grid-template-columns:repeat(3, minmax(0, 1fr));
    gap:8px !important;
  }}
  .hud-k {{ font-size:8px; }}
  .hud-v {{ font-size:18px; }}
  .xpbar {{ width:110px; }}

  .panel {{
    padding:10px;
  }}
  .panel h4 {{
    font-size:9px;
    line-height:1.5;
  }}

  .fleet-card {{
    padding:7px 8px;
  }}
  .fleet-row .thumb {{
    width:58px;
  }}
  .fleet-id {{
    font-size:18px;
  }}

  .metric {{
    min-height:88px;
    padding:7px 8px;
  }}
  .metric .v {{
    font-size:28px;
  }}
  .metric .v.big {{
    font-size:36px;
  }}

  .stButton > button {{
    font-size:18px;
  }}
  div.element-container:has(#flight-anchor) + div.element-container button,
  div.element-container:has(#maint-anchor) + div.element-container button {{
    min-height:58px !important;
  }}
  div.element-container:has(.sensor-zone) + div.element-container button {{
    height:58px;
    font-size:16px;
  }}

  .legend {{
    font-size:10px;
    line-height:1.75;
    margin:10px 0 14px 0;
    padding-bottom:4px;
    display:block;
    position:relative;
    z-index:2;
  }}

  iframe[title*="streamlit_image_coordinates"] {{
    width:100% !important;
    height:auto !important;
    aspect-ratio:{config.SCENE_W} / {config.SCENE_H};
    display:block;
  }}

  .lobby-hero {{
    padding:16px 4px 4px;
  }}
  .lobby-hero .t {{
    font-size:18px;
    line-height:1.5;
  }}
  .lobby-hero .s {{
    font-size:13px;
  }}
  .kpi {{
    padding:10px;
  }}
  .kpi .v {{
    font-size:28px;
  }}
  .notice-overlay {{
    padding:12px;
  }}
  .notice-toast {{
    width:calc(100vw - 24px);
    min-height:140px;
    padding:22px 18px 78px 18px;
    font-size:20px;
  }}
  div.element-container:has(#notice-ok-anchor) + div.element-container {{
    bottom:calc(50% - 126px);
  }}

  .report-overlay {{
    align-items:flex-start;
    padding:12px;
    overflow:auto;
  }}
  .report-modal {{
    width:calc(100vw - 24px);
    max-height:calc(100vh - 118px);
    margin-top:10px;
  }}
  .report h3 {{
    font-size:11px;
    line-height:1.6;
  }}
  div.element-container:has(#report-ok-anchor) + div.element-container,
  div.element-container:has(#report-summary-anchor) + div.element-container {{
    position:fixed;
    z-index:10000;
    left:12px !important;
    width:calc(50vw - 18px) !important;
    bottom:12px !important;
  }}
  div.element-container:has(#report-summary-anchor) + div.element-container {{
    left:calc(50vw + 6px) !important;
  }}
}}

@media (max-width: 900px) and (orientation: landscape) {{
  .block-container {{
    padding-top:0.3rem;
  }}
  .hud {{
    margin-bottom:6px;
  }}
  .hud-title {{
    font-size:10px;
  }}
  .hud-k {{
    font-size:7px;
  }}
  .hud-v {{
    font-size:16px;
  }}
  .panel {{
    padding:8px;
  }}
  .report-modal {{
    max-height:calc(100vh - 86px);
  }}
}}

@media (max-width: 900px) and (orientation: landscape) and (max-height: 450px) {{
  iframe[title*="streamlit_image_coordinates"] {{
    width:min(100%, 390px) !important;
    margin:0 auto;
  }}
}}
</style>
"""
