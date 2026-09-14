from pathlib import Path
import sys
import textwrap

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics import transit_threshold, arrival_shock_by_mandi
from src.risk_engine import get_dashboard_risk, stress_label, action_engine
from src.agent import run_question

DB_PATH = ROOT / "data" / "datops.duckdb"

st.set_page_config(
    page_title="DatOps | Mandi Intelligence",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_html(content):
    """Render HTML directly so Streamlit never interprets it as Markdown code."""
    st.html(textwrap.dedent(content))

# -----------------------------------------------------------------------------
# UI THEME
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# UI THEME — DATOPS COMMAND CENTER
# -----------------------------------------------------------------------------
render_html("""
<style>
:root{
    --bg:#070b14;
    --bg2:#0b1220;
    --panel:#0f1728;
    --panel2:#131d31;
    --panel3:#18243b;
    --line:rgba(148,163,184,.16);
    --line-strong:rgba(96,165,250,.28);
    --text:#f7f9ff;
    --muted:#9aa8bd;
    --blue:#4da3ff;
    --cyan:#58d6ff;
    --purple:#9b7cff;
    --pink:#e879f9;
    --green:#42e6a4;
    --amber:#f4c95d;
    --red:#ff6f7d;
}

html,body,[class*="css"]{
    font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
.stApp{
    background:
        radial-gradient(900px 420px at 78% -8%,rgba(74,144,226,.13),transparent 62%),
        radial-gradient(700px 430px at 18% 10%,rgba(126,87,194,.10),transparent 64%),
        linear-gradient(180deg,#070b14 0%,#080d17 55%,#060a12 100%);
    color:var(--text);
}
.block-container{
    max-width:1580px;
    padding:1rem 1.5rem 4rem;
}
header[data-testid="stHeader"]{background:rgba(7,11,20,.45);}
footer{visibility:hidden;}

/* Top navigation: sticky command bar */
div[data-testid="stTabs"]{
    position:sticky;
    top:0;
    z-index:999;
    padding:.35rem .55rem .25rem;
    margin:-.35rem -.55rem 1.05rem;
    background:rgba(7,11,20,.88);
    backdrop-filter:blur(18px);
    -webkit-backdrop-filter:blur(18px);
    border-bottom:1px solid rgba(96,165,250,.14);
}
div[data-testid="stTabs"] > div > div{
    gap:.25rem;
}
div[data-testid="stTabs"] button{
    border-radius:11px;
    color:#93a3ba;
    font-weight:750;
    font-size:.78rem;
    padding:.58rem .82rem;
    transition:.18s ease;
}
div[data-testid="stTabs"] button:hover{
    color:#eef5ff;
    background:rgba(77,163,255,.08);
}
div[data-testid="stTabs"] button[aria-selected="true"]{
    color:#fff;
    background:linear-gradient(135deg,rgba(77,163,255,.19),rgba(155,124,255,.14));
    box-shadow:inset 0 -2px 0 var(--blue),0 8px 25px rgba(0,0,0,.18);
}

/* Sidebar */
section[data-testid="stSidebar"]{
    background:
        linear-gradient(180deg,#09101d 0%,#080e18 60%,#070b14 100%);
    border-right:1px solid rgba(148,163,184,.12);
}
section[data-testid="stSidebar"] > div{
    padding:1.1rem .85rem 1.5rem;
}
section[data-testid="stSidebar"] *{color:#e8eef9;}
.sidebar-brand{
    padding:.2rem .25rem .75rem;
}
.sidebar-logo{
    color:#f8fbff;
    font-size:1.55rem;
    line-height:1;
    font-weight:900;
    letter-spacing:-.045em;
}
.sidebar-kicker{
    color:#70b7ff;
    font-size:.66rem;
    font-weight:850;
    letter-spacing:.13em;
    margin-top:.35rem;
    text-transform:uppercase;
}
.sidebar-caption{
    color:#7e8da4;
    font-size:.73rem;
    line-height:1.45;
    margin-top:.5rem;
}
.sidebar-section{
    color:#8fa4c0;
    font-size:.67rem;
    font-weight:850;
    letter-spacing:.13em;
    text-transform:uppercase;
    margin:1rem 0 .42rem;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{
    color:#b9c6d9 !important;
    font-size:.73rem !important;
    font-weight:700 !important;
}
section[data-testid="stSidebar"] .stMultiSelect,
section[data-testid="stSidebar"] .stDateInput{
    margin-bottom:.55rem;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div{
    background:#101a2b !important;
    border:1px solid rgba(148,163,184,.13) !important;
    border-radius:10px !important;
}
section[data-testid="stSidebar"] input{
    color:#f4f7fc !important;
}
section[data-testid="stSidebar"] hr{
    border-color:rgba(148,163,184,.11);
}
.filter-summary{
    padding:.7rem .8rem;
    border:1px solid rgba(77,163,255,.13);
    border-radius:12px;
    background:linear-gradient(135deg,rgba(77,163,255,.07),rgba(155,124,255,.05));
    color:#8fa4c0;
    font-size:.69rem;
    line-height:1.45;
}
.filter-summary b{color:#eaf3ff;}
.side-stat-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:.45rem;
    margin-top:.65rem;
}
.side-stat{
    padding:.65rem;
    border-radius:11px;
    background:rgba(255,255,255,.025);
    border:1px solid rgba(148,163,184,.09);
}
.side-stat-value{font-size:1rem;font-weight:850;color:#f3f7ff;}
.side-stat-label{font-size:.61rem;color:#7f8ea4;margin-top:.15rem;}

/* Hero */
.hero{
    position:relative;
    overflow:hidden;
    padding:1.8rem 1.9rem;
    margin-bottom:1rem;
    border-radius:22px;
    border:1px solid rgba(96,165,250,.20);
    background:
        radial-gradient(circle at 88% 10%,rgba(77,163,255,.18),transparent 28%),
        linear-gradient(135deg,#101a2e 0%,#0c1424 54%,#15122c 100%);
    box-shadow:0 22px 70px rgba(0,0,0,.28);
}
.hero:before{
    content:"";
    position:absolute;
    width:480px;height:480px;
    right:-230px;top:-300px;
    border-radius:50%;
    border:1px solid rgba(96,165,250,.12);
    box-shadow:0 0 0 55px rgba(96,165,250,.025),0 0 0 110px rgba(155,124,255,.018);
}
.hero-grid{
    display:grid;
    grid-template-columns:1fr auto;
    gap:1.5rem;
    align-items:end;
    position:relative;
    z-index:2;
}
.hero-kicker{
    color:#6bb7ff;
    font-size:.67rem;
    font-weight:900;
    letter-spacing:.18em;
    margin-bottom:.5rem;
}
.hero-title{
    color:#f9fbff;
    font-size:2.55rem;
    line-height:1.02;
    font-weight:900;
    letter-spacing:-.045em;
    margin:0 0 .55rem;
}
.hero-subtitle{
    color:#aebbd0;
    font-size:.91rem;
    line-height:1.55;
    max-width:900px;
}
.scope-pill{
    display:inline-block;
    margin-top:1rem;
    padding:.42rem .72rem;
    border-radius:999px;
    border:1px solid rgba(77,163,255,.18);
    background:rgba(77,163,255,.07);
    color:#b8d8ff;
    font-size:.67rem;
    font-weight:750;
}
.hero-terminal{
    min-width:165px;
    padding:.85rem 1rem;
    border-radius:15px;
    background:rgba(5,10,19,.34);
    border:1px solid rgba(148,163,184,.10);
    text-align:right;
}
.hero-terminal-label{color:#71839c;font-size:.6rem;text-transform:uppercase;letter-spacing:.12em;}
.hero-terminal-value{color:#f5f8ff;font-size:1.25rem;font-weight:900;margin-top:.18rem;}
.hero-terminal-sub{color:#4ee3ad;font-size:.65rem;font-weight:750;margin-top:.15rem;}

/* KPI */
[data-testid="stMetric"]{
    background:linear-gradient(145deg,#111b2d,#0c1422);
    border:1px solid rgba(148,163,184,.13);
    border-radius:15px;
    padding:.9rem 1rem;
    box-shadow:0 10px 30px rgba(0,0,0,.18);
    min-height:94px;
}
[data-testid="stMetricLabel"]{color:#8798b0 !important;font-size:.69rem;font-weight:750;}
[data-testid="stMetricValue"]{color:#f5f8ff !important;font-size:1.55rem;font-weight:900;letter-spacing:-.025em;}

/* Cards / sections */
.section-title{color:#f4f7fc;font-size:1.18rem;font-weight:900;letter-spacing:-.025em;margin-top:.8rem;margin-bottom:.12rem;}
.section-subtitle{color:#8291a8;font-size:.78rem;margin-bottom:.7rem;}
.section-ribbon{display:flex;align-items:center;gap:.6rem;margin:1rem 0 .65rem;}
.section-ribbon .tag{color:#75baff;font-size:.65rem;font-weight:850;letter-spacing:.12em;text-transform:uppercase;}
.section-ribbon .line{height:1px;flex:1;background:linear-gradient(90deg,rgba(77,163,255,.25),transparent);}

.watch-card,.signal{
    background:linear-gradient(145deg,#101b2e,#0c1422);
    border:1px solid rgba(148,163,184,.12);
    border-radius:15px;
    box-shadow:0 12px 35px rgba(0,0,0,.15);
}
.watch-card{padding:1rem;}
.signal{padding:1rem 1.1rem;}
.signal-title{color:#f4f7fc;font-weight:850;font-size:.88rem;}
.signal-text{color:#aab7ca;font-size:.79rem;line-height:1.5;}
.command-label{color:#6eb8ff;font-size:.64rem;font-weight:850;letter-spacing:.11em;text-transform:uppercase;}
.small{color:#91a0b5;font-size:.76rem;line-height:1.45;}
.watch-chip{
    display:inline-block;
    margin-top:.75rem;
    padding:.28rem .5rem;
    border-radius:999px;
    border:1px solid rgba(77,163,255,.16);
    background:rgba(77,163,255,.06);
    color:#83bbf1;
    font-size:.58rem;
    font-weight:800;
}

/* AgriQuery widget */
.agq-shell{
    position:relative;
    overflow:hidden;
    padding:1.15rem;
    border-radius:20px;
    border:1px solid rgba(77,163,255,.24);
    background:
        radial-gradient(circle at 92% 0%,rgba(155,124,255,.16),transparent 32%),
        linear-gradient(145deg,#101a30,#0b1322);
    box-shadow:0 18px 55px rgba(0,0,0,.24);
}
.agq-kicker{color:#72b9ff;font-size:.62rem;font-weight:900;letter-spacing:.15em;text-transform:uppercase;}
.agq-title{color:#f8fbff;font-size:1.65rem;font-weight:900;letter-spacing:-.035em;margin-top:.18rem;}
.agq-copy{color:#91a1b8;font-size:.76rem;line-height:1.45;margin-top:.25rem;max-width:850px;}
.agq-flow{margin-top:.7rem;color:#8fbfff;font-size:.63rem;font-weight:850;letter-spacing:.08em;}
.agq-flow span{color:#647a98;margin:0 .25rem;}
.agq-examples-title{color:#8fa4c0;font-size:.68rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;margin:.75rem 0 .4rem;}
.agq-example{
    padding:.68rem .72rem;
    min-height:58px;
    border-radius:12px;
    border:1px solid rgba(148,163,184,.10);
    background:rgba(255,255,255,.025);
    color:#c9d6e8;
    font-size:.69rem;
    line-height:1.35;
}

/* Make text input feel like a command widget */
div[data-testid="stTextInput"]{
    margin-top:.65rem;
}
div[data-testid="stTextInput"] label{
    display:none;
}
div[data-testid="stTextInput"] > div{
    background:linear-gradient(135deg,#111d34,#0d1729) !important;
    border:1px solid rgba(77,163,255,.38) !important;
    border-radius:16px !important;
    box-shadow:0 0 0 1px rgba(77,163,255,.04),0 14px 40px rgba(0,0,0,.20) !important;
    min-height:76px;
}
div[data-testid="stTextInput"] input{
    color:#f7faff !important;
    font-size:.92rem !important;
    padding:1rem 1.1rem !important;
}
div[data-testid="stTextInput"] input::placeholder{color:#65758d !important;}

/* Tables */
[data-testid="stDataFrame"]{
    border:1px solid rgba(148,163,184,.10);
    border-radius:13px;
    overflow:hidden;
}

/* Buttons */
.stButton > button{
    border-radius:10px;
    border:1px solid rgba(77,163,255,.20);
    background:linear-gradient(135deg,rgba(77,163,255,.12),rgba(155,124,255,.10));
    color:#dcecff;
    font-weight:750;
}
.stButton > button:hover{
    border-color:rgba(77,163,255,.55);
    color:#fff;
    box-shadow:0 8px 25px rgba(77,163,255,.10);
}

/* Responsive */
@media(max-width:900px){
    .hero-grid{grid-template-columns:1fr;}
    .hero-terminal{text-align:left;}
    .hero-title{font-size:2rem;}
    div[data-testid="stTabs"] button{font-size:.68rem;padding:.48rem .55rem;}
}

@media(min-width:900px){
 section[data-testid="stSidebar"]{width:292px !important; min-width:292px !important; max-width:292px !important;}
 section[data-testid="stSidebar"] > div{width:292px !important;}
}
section[data-testid="stSidebar"]{pointer-events:auto !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"]{margin-bottom:.5rem !important;}
section[data-testid="stSidebar"] [data-testid="stExpanderDetails"]{padding:.3rem .2rem .65rem !important;}
</style>
<style>
/* DATOPS FINAL STRUCTURAL FIXES */
.block-container{width:100% !important;max-width:none !important;margin:0 !important;}
/* Only the tab strip sticks; tab content stays in normal flow. */
div[data-testid="stTabs"]{position:relative !important;overflow:visible !important;z-index:20 !important;}
div[data-testid="stTabs"] [role="tablist"]{position:sticky !important;top:0 !important;z-index:100000 !important;overflow-x:auto !important;overflow-y:hidden !important;pointer-events:auto !important;isolation:isolate !important;background:rgba(5,8,18,.97) !important;backdrop-filter:blur(20px) !important;-webkit-backdrop-filter:blur(20px) !important;}
div[data-testid="stTabs"] [role="tab"]{pointer-events:auto !important;position:relative !important;z-index:100001 !important;min-height:48px !important;padding:.65rem .9rem !important;}
/* When Streamlit collapses its native sidebar, release its reserved width. */
section[data-testid="stSidebar"][aria-expanded="false"]{width:0 !important;min-width:0 !important;max-width:0 !important;overflow:visible !important;}
section[data-testid="stSidebar"][aria-expanded="false"] > div{width:0 !important;min-width:0 !important;padding:0 !important;overflow:hidden !important;}
/* Never let the collapsed sidebar create a phantom left gutter. */
[data-testid="stAppViewContainer"] > .main{margin-left:0 !important;}
/* Compact, high-contrast nav without template clutter. */
div[data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar{height:0 !important;}
</style>


<style>
/* ================= DATOPS V5 PRODUCT UI ================= */
:root{
  --ink:#f7f9ff;
  --muted:#8e9bb0;
  --subtle:#66748b;
  --canvas:#050812;
  --surface:#0b1220;
  --surface2:#10192b;
  --surface3:#151f34;
  --blue:#4da3ff;
  --cyan:#57d7ff;
  --violet:#9b7cff;
  --amber:#f3c969;
  --red:#ff6d7d;
  --green:#42e6a4;
  --border:rgba(148,163,184,.14);
  --border2:rgba(77,163,255,.28);
}

html,body,[class*="css"]{
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif !important;
}
.stApp{
  background:
    radial-gradient(850px 500px at 82% -8%,rgba(64,119,255,.13),transparent 62%),
    radial-gradient(650px 420px at 18% 25%,rgba(137,92,255,.07),transparent 65%),
    #050812 !important;
}
.block-container{
  width:100% !important;
  max-width:none !important;
  padding:1.2rem 1.25rem 4rem !important;
}

/* ---------- FLOATING NAV ---------- */
div[data-testid="stTabs"]{
  position:relative !important;
  z-index:2 !important;
  margin:0 !important;
  padding-top:3.9rem !important;
}
div[data-testid="stTabs"] [role="tablist"]{
  position:fixed !important;
  top:0 !important; left:0 !important; right:0 !important;
  z-index:100000 !important;
  display:flex !important; align-items:center !important; justify-content:center !important;
  gap:.18rem !important; min-height:58px !important;
  padding:.42rem 1rem !important; margin:0 !important;
  background:rgba(5,8,18,.96) !important;
  backdrop-filter:blur(20px) saturate(150%) !important;
  -webkit-backdrop-filter:blur(20px) saturate(150%) !important;
  border-bottom:1px solid rgba(148,163,184,.12) !important;
  box-shadow:0 10px 30px rgba(0,0,0,.28) !important;
  pointer-events:auto !important;
}
div[data-testid="stTabs"] [role="tablist"] button{pointer-events:auto !important;}
div[data-testid="stTabs"] > div{
  max-width:1640px;
  margin:0 auto;
}
div[data-testid="stTabs"] [role="tablist"]{
  gap:.18rem !important;
}
div[data-testid="stTabs"] button{
  color:#8d9ab0 !important;
  border-radius:10px !important;
  font-size:.76rem !important;
  font-weight:750 !important;
  padding:.58rem .72rem !important;
  border:1px solid transparent !important;
}
div[data-testid="stTabs"] button:hover{
  color:#fff !important;
  background:rgba(77,163,255,.08) !important;
}
div[data-testid="stTabs"] button[aria-selected="true"]{
  color:#fff !important;
  background:linear-gradient(135deg,rgba(77,163,255,.18),rgba(155,124,255,.14)) !important;
  border-color:rgba(77,163,255,.22) !important;
  box-shadow:inset 0 -2px 0 var(--blue),0 6px 20px rgba(0,0,0,.2) !important;
}

/* ---------- SIDEBAR / CONTROL PANEL ---------- */
section[data-testid="stSidebar"]{
  z-index:10050 !important;
  background:linear-gradient(180deg,#080d18 0%,#060a13 100%) !important;
  border-right:1px solid rgba(148,163,184,.11) !important;
  pointer-events:auto !important;
}
section[data-testid="stSidebar"] > div{
  padding:.85rem .8rem 1.25rem !important;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"]{
  margin-bottom:.22rem !important;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{
  color:#b7c4d7 !important;
  font-size:.70rem !important;
  font-weight:750 !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div{
  background:#0d1524 !important;
  border:1px solid rgba(148,163,184,.13) !important;
  border-radius:10px !important;
  min-height:40px !important;
  box-shadow:none !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover{
  border-color:rgba(77,163,255,.38) !important;
}
section[data-testid="stSidebar"] input{
  color:#f4f7fc !important;
}
section[data-testid="stSidebar"] .stButton button{
  width:100% !important;
  border-radius:10px !important;
  min-height:38px !important;
}
.side-brand-v5{
  padding:.45rem .3rem .9rem;
  border-bottom:1px solid rgba(148,163,184,.10);
  margin-bottom:.85rem;
}
.side-brand-v5 .name{
  font-size:1.38rem;font-weight:900;letter-spacing:-.04em;color:#f7f9ff;
}
.side-brand-v5 .sub{
  margin-top:.15rem;color:#65b5ff;font-size:.61rem;font-weight:850;
  letter-spacing:.15em;text-transform:uppercase;
}
.side-heading-v5{
  color:#71839c;font-size:.62rem;font-weight:900;letter-spacing:.15em;
  text-transform:uppercase;margin:.9rem .15rem .45rem;
}
.side-scope-v5{
  padding:.75rem;border:1px solid rgba(77,163,255,.16);
  background:linear-gradient(135deg,rgba(77,163,255,.07),rgba(155,124,255,.04));
  border-radius:12px;margin-top:.65rem;
}
.side-scope-v5 .big{font-size:.76rem;font-weight:800;color:#eaf3ff}
.side-scope-v5 .small{font-size:.62rem;color:#75869d;line-height:1.45;margin-top:.18rem}
.side-mini-grid{
  display:grid;grid-template-columns:1fr 1fr;gap:.4rem;margin-top:.5rem;
}
.side-mini{
  padding:.58rem;border-radius:10px;background:#0c1422;
  border:1px solid rgba(148,163,184,.08);
}
.side-mini .v{font-size:.86rem;font-weight:850;color:#eaf3ff}
.side-mini .l{font-size:.56rem;color:#667891;text-transform:uppercase;letter-spacing:.08em;margin-top:.1rem}

/* ---------- HERO ---------- */
.hero{
  background:
    radial-gradient(500px 240px at 92% 5%,rgba(77,163,255,.16),transparent 65%),
    linear-gradient(135deg,#0c1424 0%,#0b1120 60%,#11132b 100%) !important;
  border:1px solid rgba(77,163,255,.20) !important;
  border-radius:24px !important;
  box-shadow:0 24px 70px rgba(0,0,0,.28) !important;
}
.hero-kicker{color:#68b8ff !important}
.hero-title{font-size:2.75rem !important}
.hero-terminal{display:none !important}
.scope-pill{
  color:#b8d8ff !important;
  background:rgba(77,163,255,.07) !important;
  border-color:rgba(77,163,255,.20) !important;
}

/* ---------- KPI / SIGNAL CARDS ---------- */
div[data-testid="stMetric"]{
  background:linear-gradient(145deg,#0c1525,#0a111d) !important;
  border:1px solid rgba(148,163,184,.12) !important;
  border-radius:16px !important;
  padding:1rem 1.05rem !important;
  min-height:104px;
  box-shadow:0 10px 28px rgba(0,0,0,.14);
}
div[data-testid="stMetricLabel"]{
  color:#8393aa !important;
  font-size:.69rem !important;
  font-weight:700 !important;
}
div[data-testid="stMetricValue"]{
  color:#f7f9ff !important;
  font-weight:900 !important;
  letter-spacing:-.035em !important;
}
.signal,.watch-card,.command-card{
  background:linear-gradient(145deg,#0d1728,#0a111e) !important;
  border:1px solid rgba(148,163,184,.12) !important;
  border-radius:16px !important;
  box-shadow:0 12px 32px rgba(0,0,0,.16) !important;
}
.signal{padding:1rem 1.05rem !important}
.command-strip{
  display:grid !important;
  grid-template-columns:repeat(4,minmax(0,1fr)) !important;
  gap:.75rem !important;
  margin:.35rem 0 1.25rem !important;
}
.command-card{padding:1rem 1.05rem !important;min-height:142px !important;position:relative;overflow:hidden}
.command-card:before{
  content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--blue);opacity:.85;
}
.command-card.gold:before{background:var(--amber)}
.command-card.blue:before{background:var(--cyan)}
.command-card.violet:before{background:var(--violet)}
.command-label{color:#7fa1c6 !important;font-size:.60rem !important;font-weight:850 !important;letter-spacing:.12em !important;text-transform:uppercase}
.command-value{font-size:1.45rem !important;font-weight:900 !important;letter-spacing:-.035em !important;color:#f7f9ff !important;margin-top:.38rem}
.command-delta{font-size:.72rem !important;font-weight:800 !important;color:#66b8ff !important;margin-top:.22rem}
.command-delta.warn{color:var(--amber) !important}
.command-delta.neutral{color:#aab8ca !important}
.command-note{font-size:.62rem !important;line-height:1.45 !important;color:#718198 !important;margin-top:.35rem}
.section-title{color:#f4f7ff !important;font-size:1.12rem !important}
.section-subtitle{color:#75869e !important}

/* ---------- AGENT WORKSPACE ---------- */
.agq-shell{
  padding:1.35rem !important;
  border-radius:22px !important;
  background:
    radial-gradient(500px 250px at 100% 0%,rgba(155,124,255,.14),transparent 68%),
    linear-gradient(145deg,#0d1628,#09111e) !important;
  border:1px solid rgba(77,163,255,.22) !important;
  box-shadow:0 22px 65px rgba(0,0,0,.25) !important;
}
.agq-kicker{color:#68b8ff !important}
.agq-title{font-size:2rem !important}
.agq-copy{font-size:.80rem !important;color:#93a2b8 !important}
.agq-flow{color:#8dc4ff !important}
.agq-examples-title{margin-top:1rem !important;color:#8fa7c4 !important}
div[data-testid="stTextInput"]{
  margin-top:.35rem !important;
}
div[data-testid="stTextInput"] > div{
  min-height:86px !important;
  background:linear-gradient(135deg,#111d33,#0c1628) !important;
  border:1px solid rgba(77,163,255,.48) !important;
  border-radius:18px !important;
  box-shadow:0 0 0 1px rgba(77,163,255,.05),0 18px 50px rgba(0,0,0,.25) !important;
}
div[data-testid="stTextInput"] input{
  font-size:1rem !important;
  padding:1.25rem !important;
  color:#f8fbff !important;
}
div[data-testid="stTextInput"] input::placeholder{color:#62738b !important}
div[data-testid="stButton"] button{
  border-radius:11px !important;
  border:1px solid rgba(148,163,184,.14) !important;
  background:#0e1728 !important;
  color:#cbd8e9 !important;
  font-weight:750 !important;
}
div[data-testid="stButton"] button:hover{
  border-color:rgba(77,163,255,.35) !important;
  background:#132039 !important;
  color:#fff !important;
}
.agq-command-row{
  display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:.65rem;margin:.75rem 0;
}
.agq-mini{
  padding:.75rem;border:1px solid rgba(148,163,184,.10);border-radius:12px;
  background:rgba(255,255,255,.025);
}
.agq-mini .k{font-size:.58rem;color:#687b95;text-transform:uppercase;letter-spacing:.11em;font-weight:850}
.agq-mini .v{font-size:.76rem;color:#e9f1fc;font-weight:750;margin-top:.25rem}

/* ---------- TABLES / CHARTS ---------- */
div[data-testid="stDataFrame"]{
  border:1px solid rgba(148,163,184,.10) !important;
  border-radius:14px !important;
  overflow:hidden !important;
}
.stPlotlyChart{
  border-radius:15px;
  overflow:hidden;
}

/* ---------- MOBILE ---------- */
@media(max-width:1000px){
  .block-container{padding-left:.8rem !important;padding-right:.8rem !important}
  .command-strip{grid-template-columns:1fr 1fr !important}
  .hero-title{font-size:2rem !important}
}
@media(max-width:650px){
  .command-strip{grid-template-columns:1fr !important}
  div[data-testid="stTabs"] button{font-size:.66rem !important;padding:.48rem .45rem !important}
}
</style>

""")


render_html(r"""
<style>
/* DATOPS V7: stable, clickable sticky navigation */
div[data-testid="stTabs"]{
  position:relative !important;
  z-index:10 !important;
  margin:0 !important;
  padding:0 !important;
  background:transparent !important;
}
div[data-testid="stTabs"] [role="tablist"]{
  position:sticky !important;
  top:0 !important;
  z-index:1000 !important;
  width:100% !important;
  min-height:54px !important;
  display:flex !important;
  align-items:center !important;
  justify-content:flex-start !important;
  gap:.22rem !important;
  padding:.35rem .35rem !important;
  margin:0 0 1rem 0 !important;
  background:rgba(5,8,18,.96) !important;
  border:1px solid rgba(148,163,184,.12) !important;
  border-radius:0 0 14px 14px !important;
  backdrop-filter:blur(20px) saturate(150%) !important;
  -webkit-backdrop-filter:blur(20px) saturate(150%) !important;
  box-shadow:0 10px 30px rgba(0,0,0,.24) !important;
  overflow-x:auto !important;
  overflow-y:hidden !important;
  pointer-events:auto !important;
}
div[data-testid="stTabs"] [role="tablist"] button{
  position:relative !important;
  z-index:1001 !important;
  pointer-events:auto !important;
  flex:0 0 auto !important;
  min-height:40px !important;
  height:40px !important;
  padding:.55rem .8rem !important;
  border-radius:9px !important;
  border:1px solid transparent !important;
  color:#8e9bb0 !important;
  font-size:.75rem !important;
  font-weight:760 !important;
  line-height:1 !important;
  white-space:nowrap !important;
  cursor:pointer !important;
}
div[data-testid="stTabs"] [role="tablist"] button:hover{
  color:#fff !important;
  background:rgba(77,163,255,.09) !important;
}
div[data-testid="stTabs"] [role="tablist"] button[aria-selected="true"]{
  color:#fff !important;
  background:linear-gradient(135deg,rgba(77,163,255,.19),rgba(155,124,255,.14)) !important;
  border-color:rgba(77,163,255,.22) !important;
  box-shadow:inset 0 -2px 0 #4da3ff !important;
}
/* Main content must remain in normal document flow so the page scrolls. */
div[data-testid="stTabs"] > div{position:relative !important;}
/* Compact decision cockpit */
.command-strip{grid-template-columns:repeat(4,minmax(0,1fr)) !important;gap:.65rem !important;margin:.35rem 0 1.25rem !important;}
.command-card{min-height:122px !important;padding:.88rem .95rem !important;}
.command-value{font-size:1.28rem !important;}
.command-note{font-size:.60rem !important;line-height:1.35 !important;}
/* Real command widget */
div[data-testid="stTextArea"] > div{
  background:linear-gradient(145deg,#101a2c,#0b1423) !important;
  border:1px solid rgba(77,163,255,.42) !important;
  border-radius:16px !important;
  box-shadow:0 16px 42px rgba(0,0,0,.22) !important;
}
div[data-testid="stTextArea"] textarea{
  min-height:104px !important;
  padding:1rem !important;
  font-size:1rem !important;
  line-height:1.5 !important;
  color:#f7f9ff !important;
  background:transparent !important;
}
@media(max-width:900px){.command-strip{grid-template-columns:1fr 1fr !important;}}
@media(max-width:600px){.command-strip{grid-template-columns:1fr !important;}}

/* ================================================================
   DATOPS V8 — FINAL PRODUCT POLISH
   ================================================================ */

/* Navigation: compact, full-hit-area, calm glass bar */
div[data-testid="stTabs"]{
    position:sticky !important;
    top:0 !important;
    z-index:10020 !important;
    margin:-.35rem -.45rem 1.05rem !important;
    padding:.34rem .42rem .28rem !important;
    background:rgba(5,8,18,.93) !important;
    border:0 !important;
    border-bottom:1px solid rgba(120,145,180,.13) !important;
    box-shadow:0 10px 28px rgba(0,0,0,.18) !important;
    backdrop-filter:blur(20px) saturate(150%) !important;
    -webkit-backdrop-filter:blur(20px) saturate(150%) !important;
}
div[data-testid="stTabs"] > div{
    min-height:46px !important;
}
div[data-testid="stTabs"] [role="tablist"]{
    display:flex !important;
    align-items:center !important;
    gap:.18rem !important;
    padding:.08rem !important;
    overflow-x:auto !important;
    scrollbar-width:none !important;
}
div[data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar{display:none !important;}
div[data-testid="stTabs"] button,
div[data-testid="stTabs"] [role="tab"]{
    position:relative !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    min-height:42px !important;
    height:42px !important;
    padding:.55rem .82rem !important;
    margin:0 !important;
    border-radius:9px !important;
    border:1px solid transparent !important;
    color:#8290a6 !important;
    background:transparent !important;
    font-size:.74rem !important;
    font-weight:760 !important;
    letter-spacing:.005em !important;
    white-space:nowrap !important;
    cursor:pointer !important;
    pointer-events:auto !important;
    box-sizing:border-box !important;
}
div[data-testid="stTabs"] button:hover,
div[data-testid="stTabs"] [role="tab"]:hover{
    color:#e9f2ff !important;
    background:rgba(86,143,220,.08) !important;
    border-color:rgba(86,143,220,.12) !important;
}
div[data-testid="stTabs"] button[aria-selected="true"],
div[data-testid="stTabs"] [role="tab"][aria-selected="true"]{
    color:#f7fbff !important;
    background:linear-gradient(135deg,rgba(70,151,255,.16),rgba(151,111,255,.12)) !important;
    border-color:rgba(91,157,255,.22) !important;
    box-shadow:0 5px 18px rgba(0,0,0,.16) !important;
}
div[data-testid="stTabs"] button[aria-selected="true"]::after,
div[data-testid="stTabs"] [role="tab"][aria-selected="true"]::after{
    content:"" !important;
    position:absolute !important;
    left:12px !important;
    right:12px !important;
    bottom:2px !important;
    height:2px !important;
    border-radius:3px !important;
    background:linear-gradient(90deg,#55aaff,#a67cff) !important;
}

/* Make the main document breathe correctly around the sticky nav. */
.block-container{
    padding-top:4.35rem !important;
    padding-bottom:3.5rem !important;
}

/* Sidebar: narrower, denser, more control-room-like. */
section[data-testid="stSidebar"]{
    width:292px !important;
    min-width:292px !important;
    max-width:292px !important;
}
section[data-testid="stSidebar"] > div{
    width:292px !important;
    padding:.82rem .72rem 1.2rem !important;
}
.sidebar-brand{
    padding:.15rem .2rem .62rem !important;
    margin-bottom:.45rem !important;
}
.sidebar-logo{font-size:1.38rem !important;}
.sidebar-kicker{font-size:.59rem !important;letter-spacing:.15em !important;}
.sidebar-section{margin:.72rem 0 .32rem !important;font-size:.61rem !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"]{
    border:1px solid rgba(148,163,184,.11) !important;
    border-radius:11px !important;
    background:rgba(12,19,32,.56) !important;
    margin:.42rem 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary{
    min-height:39px !important;
    padding:.55rem .65rem !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p{
    font-size:.70rem !important;
    font-weight:800 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpanderDetails"]{
    padding:.15rem .58rem .62rem !important;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"]{
    margin-bottom:.16rem !important;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{
    font-size:.66rem !important;
    color:#8fa0b7 !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div{
    min-height:37px !important;
    border-radius:9px !important;
    background:#0c1422 !important;
}
section[data-testid="stSidebar"] .stMultiSelect,
section[data-testid="stSidebar"] .stDateInput{
    margin-bottom:.38rem !important;
}
section[data-testid="stSidebar"] .stButton button{
    min-height:35px !important;
    font-size:.70rem !important;
}

/* Hero: less empty vertical space, more information density. */
.hero{
    padding:1.35rem 1.55rem !important;
    min-height:0 !important;
    margin-bottom:.85rem !important;
    border-radius:19px !important;
    background:
      radial-gradient(480px 220px at 92% 0%,rgba(80,128,255,.16),transparent 70%),
      linear-gradient(135deg,#0d1728 0%,#0a1220 60%,#12132a 100%) !important;
}
.hero-grid{
    gap:1rem !important;
}
.hero-kicker{font-size:.60rem !important;margin-bottom:.38rem !important;}
.hero-title{font-size:2.12rem !important;margin-bottom:.35rem !important;}
.hero-subtitle{font-size:.79rem !important;max-width:860px !important;line-height:1.45 !important;}
.scope-pill{margin-top:.72rem !important;font-size:.61rem !important;padding:.34rem .62rem !important;}

/* KPI strip: compact but high contrast. */
[data-testid="stMetric"]{
    min-height:92px !important;
    padding:.82rem .9rem !important;
    border-radius:14px !important;
}
[data-testid="stMetricLabel"]{font-size:.65rem !important;}
[data-testid="stMetricValue"]{font-size:1.48rem !important;}

/* Section hierarchy. */
.section-title{
    margin-top:.25rem !important;
    margin-bottom:.18rem !important;
}
.section-subtitle{
    font-size:.72rem !important;
    margin-bottom:.7rem !important;
}

/* Signals: stronger semantic accents without rainbow UI. */
.signal{
    min-height:118px !important;
    padding:.9rem !important;
    position:relative !important;
    overflow:hidden !important;
}
.signal:before{
    content:"" !important;
    position:absolute !important;
    left:0 !important;
    top:0 !important;
    bottom:0 !important;
    width:3px !important;
    background:#5aa9ff !important;
}
.signal:nth-child(2):before{background:#f0c66a !important;}
.signal:nth-child(3):before{background:#9b7cff !important;}

/* Decision cockpit: four compact cards, not a text wall. */
.command-strip{
    grid-template-columns:repeat(4,minmax(0,1fr)) !important;
    gap:.65rem !important;
    margin:.3rem 0 1rem !important;
}
.command-card{
    min-height:124px !important;
    padding:.82rem .9rem !important;
    border-radius:14px !important;
}
.command-value{font-size:1.28rem !important;}
.command-note{font-size:.59rem !important;}

/* Agent: make the input the visual focal point. */
.agq-shell{
    padding:1.05rem !important;
    border-radius:18px !important;
}
.agq-title{font-size:1.72rem !important;}
.agq-copy{font-size:.74rem !important;max-width:900px !important;}
.agq-flow{font-size:.66rem !important;}
.agq-command-row{
    grid-template-columns:1.35fr 1fr 1fr !important;
    gap:.55rem !important;
    margin:.65rem 0 !important;
}
.agq-mini{padding:.62rem .7rem !important;}
.agq-mini .k{font-size:.54rem !important;}
.agq-mini .v{font-size:.68rem !important;}
div[data-testid="stTextInput"] > div,
div[data-testid="stTextArea"] > div{
    min-height:74px !important;
    border-radius:15px !important;
    background:linear-gradient(135deg,#111d31,#0c1627) !important;
    border-color:rgba(82,158,255,.40) !important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea{
    font-size:.94rem !important;
    padding:1rem !important;
}

/* Tables/charts get a consistent frame. */
div[data-testid="stDataFrame"],
.stPlotlyChart{
    border-radius:13px !important;
}

/* Responsive */
@media(max-width:1100px){
    section[data-testid="stSidebar"]{width:270px !important;min-width:270px !important;max-width:270px !important;}
    section[data-testid="stSidebar"] > div{width:270px !important;}
    .command-strip{grid-template-columns:1fr 1fr !important;}
}
@media(max-width:700px){
    .block-container{padding-left:.65rem !important;padding-right:.65rem !important;}
    .hero-title{font-size:1.7rem !important;}
    .command-strip,.agq-command-row{grid-template-columns:1fr !important;}
    div[data-testid="stTabs"] button{padding:.48rem .62rem !important;font-size:.68rem !important;}
}

</style>
""")

# -----------------------------------------------------------------------------
# DATABASE
# -----------------------------------------------------------------------------

@st.cache_resource
def get_connection():
    if not DB_PATH.exists():
        st.error(f"DuckDB database not found: {DB_PATH}. Run `python src/database.py` first.")
        st.stop()
    return duckdb.connect(str(DB_PATH), read_only=True)


CON = get_connection()


@st.cache_data(ttl=300)
def load_risk_data():
    """Load explainable risk outputs for the dashboard."""
    return get_dashboard_risk()


try:
    risk_data = load_risk_data()
    mandi_risk = risk_data.get("mandi_risk", pd.DataFrame())
    weather_risk = risk_data.get("weather", pd.DataFrame())
    system_risk = risk_data.get("system", {})
    actions = risk_data.get("actions", pd.DataFrame())
except Exception as exc:
    mandi_risk = pd.DataFrame()
    weather_risk = pd.DataFrame()
    system_risk = {}
    actions = pd.DataFrame()
    st.warning(
        f"Risk engine unavailable; core analytics remain active. {exc}"
    )


def risk_status(score):
    if score is None or pd.isna(score):
        return "N/A"
    return stress_label(float(score))

@st.cache_data
def columns(table):
    return CON.execute(f"DESCRIBE {table}").fetchdf()["column_name"].tolist()

def q(sql, params=None):
    return CON.execute(sql, params or []).fetchdf()

def pick(cols, names):
    return next((x for x in names if x in cols), None)

def in_filter(column, values, params):
    if not values:
        return ""
    params.extend(values)
    return f" AND {column} IN ({','.join(['?'] * len(values))})"

AC = columns("arrivals")
PC = columns("prices")
MC = columns("mandi_master")
TC = columns("transport")

ADATE = pick(AC, ["arrival_date", "date"])
PDATE = pick(PC, ["price_date", "date"])
ACROP = pick(AC, ["crop_name", "crop"])
PCROP = pick(PC, ["crop_name", "crop"])
MID = pick(MC, ["mandi_id"])
MNAME = pick(MC, ["mandi_name", "name"])
STATE = pick(MC, ["state"])
DIST = pick(MC, ["district"])

@st.cache_data
def filter_values():
    states = q(f"SELECT DISTINCT {STATE} state FROM mandi_master WHERE {STATE} IS NOT NULL ORDER BY state")
    districts = q(f"SELECT DISTINCT {DIST} district FROM mandi_master WHERE {DIST} IS NOT NULL ORDER BY district")
    mandis = q(f"SELECT {MID} mandi_id,{MNAME} mandi_name,{DIST} district,{STATE} state FROM mandi_master ORDER BY mandi_name")
    crops = q(f"SELECT DISTINCT {ACROP} crop FROM arrivals WHERE {ACROP} IS NOT NULL ORDER BY crop")
    return states, districts, mandis, crops

@st.cache_data
def date_bounds():
    d = q(f"SELECT MIN({ADATE}) min_date,MAX({ADATE}) max_date FROM arrivals WHERE {ADATE} IS NOT NULL")
    return pd.to_datetime(d.min_date.iloc[0]).date(), pd.to_datetime(d.max_date.iloc[0]).date()

@st.cache_data
def arrivals_data(states, districts, mandis, crops, start, end):
    p = [start, end]
    where = f"WHERE a.quantity_status='VALID' AND a.arrival_quantity_qtl IS NOT NULL AND a.{ADATE} BETWEEN ? AND ?"
    where += in_filter(f"m.{STATE}", states, p)
    where += in_filter(f"m.{DIST}", districts, p)
    where += in_filter("a.mandi_id", mandis, p)
    where += in_filter(f"a.{ACROP}", crops, p)
    return q(f"""
        SELECT a.{ADATE} date,a.mandi_id,m.{MNAME} mandi_name,m.{DIST} district,
               m.{STATE} state,a.{ACROP} crop,a.arrival_quantity_qtl
        FROM arrivals a LEFT JOIN mandi_master m ON a.mandi_id=m.{MID}
        {where} ORDER BY date
    """, p)

@st.cache_data
def prices_data(states, districts, mandis, crops, start, end):
    p = [start, end]
    where = f"WHERE p.{PDATE} BETWEEN ? AND ? AND p.modal_price IS NOT NULL"
    where += in_filter(f"m.{STATE}", states, p)
    where += in_filter(f"m.{DIST}", districts, p)
    where += in_filter("p.mandi_id", mandis, p)
    where += in_filter(f"p.{PCROP}", crops, p)
    return q(f"""
        SELECT p.{PDATE} date,p.mandi_id,m.{MNAME} mandi_name,m.{DIST} district,
               m.{STATE} state,p.{PCROP} crop,p.modal_price,p.msp
        FROM prices p LEFT JOIN mandi_master m ON p.mandi_id=m.{MID}
        {where} ORDER BY date
    """, p)

@st.cache_data
def transport_data(states, districts, mandis, start, end):
    p = []
    where = "WHERE t.transit_status='VALID' AND t.transit_hours IS NOT NULL"
    if "departure_time" in TC:
        where += " AND CAST(t.departure_time AS DATE) BETWEEN ? AND ?"
        p += [start, end]
    where += in_filter(f"m.{STATE}", states, p)
    where += in_filter(f"m.{DIST}", districts, p)
    where += in_filter("t.mandi_id", mandis, p)
    return q(f"""
        SELECT t.mandi_id,m.{MNAME} mandi_name,m.{DIST} district,m.{STATE} state,
               t.transit_hours,t.distance_km,t.destination_warehouse
        FROM transport t LEFT JOIN mandi_master m ON t.mandi_id=m.{MID}
        {where}
    """, p)

@st.cache_data
def weather_data():
    return q("""
        SELECT weather_date_ist,
               AVG(temperature_c) avg_temperature_c,
               AVG(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) avg_rainfall_mm,
               MAX(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) max_rainfall_mm,
               COUNT(DISTINCT CASE WHEN rainfall_status='VALID' THEN sensor_id END) reporting_sensors,
               AVG(humidity_percent) avg_humidity
        FROM weather
        WHERE weather_date_ist IS NOT NULL
        GROUP BY weather_date_ist
        ORDER BY weather_date_ist
    """)

# -----------------------------------------------------------------------------
# CHART HELPERS
# -----------------------------------------------------------------------------


def style(fig, height=400):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter,Arial,sans-serif", color="#dbe9e3"),
        margin=dict(l=12,r=18,t=42,b=12),
        hoverlabel=dict(bgcolor="#102438", font_color="#f4fbf7"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#b9c9d3")),
    )
    fig.update_xaxes(gridcolor="rgba(148,163,184,.10)", zerolinecolor="rgba(148,163,184,.10)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,.10)", zerolinecolor="rgba(148,163,184,.10)")
    return fig


def chart(fig, height=400):
    style(fig, height)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "displaylogo": False, "responsive": True, "scrollZoom": False})


def no_data(msg):
    st.info(msg)

# -----------------------------------------------------------------------------
# FILTERS
# -----------------------------------------------------------------------------

states_df, districts_df, mandis_df, crops_df = filter_values()
MIN_DATE, MAX_DATE = date_bounds()

with st.sidebar:
    render_html("""
    <div class="side-brand-v5">
        <div class="name">🌾 DatOps</div>
        <div class="sub">Mandi Intelligence</div>
    </div>
    <div class="side-heading-v5">Control panel</div>
    """)

    with st.expander("📍 Location scope", expanded=True):
        selected_states = st.multiselect(
            "State",
            states_df.state.dropna().tolist(),
            placeholder="All states",
            key="filter_states",
        )

        available_districts = districts_df.district.dropna().tolist()
        if selected_states:
            available_districts = (
                mandis_df[mandis_df.state.isin(selected_states)]
                .district.dropna().unique().tolist()
            )

        selected_districts = st.multiselect(
            "District",
            sorted(available_districts),
            placeholder="All districts",
            key="filter_districts",
        )

        available_mandis = mandis_df.copy()
        if selected_states:
            available_mandis = available_mandis[
                available_mandis.state.isin(selected_states)
            ]
        if selected_districts:
            available_mandis = available_mandis[
                available_mandis.district.isin(selected_districts)
            ]

        mandi_options = dict(
            zip(available_mandis.mandi_name, available_mandis.mandi_id)
        )

        selected_mandi_names = st.multiselect(
            "Mandi",
            sorted(mandi_options),
            placeholder="All mandis",
            key="filter_mandis",
        )
        selected_mandis = [mandi_options[x] for x in selected_mandi_names]

        selected_crops = st.multiselect(
            "Crop",
            crops_df.crop.dropna().tolist(),
            placeholder="All crops",
            key="filter_crops",
        )

    with st.expander("🗓️ Analysis window", expanded=True):
        dates = st.date_input(
            "Arrival dates",
            value=(MIN_DATE, MAX_DATE),
            min_value=MIN_DATE,
            max_value=MAX_DATE,
            key="filter_dates",
        )

        if isinstance(dates, tuple):
            start_date, end_date = (
                dates if len(dates) == 2 else (dates[0], dates[0])
            )
        else:
            start_date = end_date = dates

    active = (
        len(selected_states)
        + len(selected_districts)
        + len(selected_mandis)
        + len(selected_crops)
    )

    scope_text = " • ".join(
        scope_parts
        for scope_parts in [
            f"{len(selected_states)} state(s)" if selected_states else "",
            f"{len(selected_districts)} district(s)" if selected_districts else "",
            f"{len(selected_mandis)} mandi(s)" if selected_mandis else "",
            ", ".join(selected_crops) if selected_crops else "",
        ]
        if scope_parts
    ) or "All available mandis and crops"

    render_html(f"""
    <div class="side-scope-v5">
        <div class="big">{'Filtered scope' if active else 'Full dataset scope'}</div>
        <div class="small">{scope_text}</div>
        <div class="small">{start_date} → {end_date}</div>
    </div>
    <div class="side-mini-grid">
        <div class="side-mini"><div class="v">{len(states_df)}</div><div class="l">states</div></div>
        <div class="side-mini"><div class="v">{len(mandis_df)}</div><div class="l">mandis</div></div>
        <div class="side-mini"><div class="v">{len(crops_df)}</div><div class="l">crops</div></div>
        <div class="side-mini"><div class="v">LIVE</div><div class="l">DuckDB</div></div>
    </div>
    """)

    if st.button("↺ Reset filters", key="reset_filters", use_container_width=True):
        for key in ["filter_states", "filter_districts", "filter_mandis", "filter_crops", "filter_dates"]:
            st.session_state.pop(key, None)
        st.rerun()


arrivals = arrivals_data(tuple(selected_states), tuple(selected_districts), tuple(selected_mandis), tuple(selected_crops), start_date, end_date)
prices = prices_data(tuple(selected_states), tuple(selected_districts), tuple(selected_mandis), tuple(selected_crops), start_date, end_date)
transport = transport_data(tuple(selected_states), tuple(selected_districts), tuple(selected_mandis), start_date, end_date)
weather = weather_data()

scope = []
if selected_states: scope.append(f"{len(selected_states)} state(s)")
if selected_districts: scope.append(f"{len(selected_districts)} district(s)")
if selected_mandis: scope.append(f"{len(selected_mandis)} mandi(s)")
if selected_crops: scope.append(", ".join(selected_crops))
scope_text = " • ".join(scope) if scope else "All available mandis and crops"

    # PRIMARY NAVIGATION
# -----------------------------------------------------------------------------

tab_overview, tab_supply, tab_price, tab_logistics, tab_weather, tab_mandi, tab_risk, tab_agriquery = st.tabs([
    "Overview", "Supply", "Market", "Logistics", "Weather",
    "Mandis", "Risk", "AgriQuery"
])

with tab_overview:

# -----------------------------------------------------------------------------
    # HERO
    # -----------------------------------------------------------------------------

    render_html(f"""
    <div class="hero">
        <div class="hero-grid">
            <div>
                <div class="hero-kicker">DATOPS · MANDI INTELLIGENCE</div>
                <div class="hero-title">🌾 DatOps</div>
                <div class="hero-subtitle">
                    Mandi intelligence for supply, market pressure, logistics and weather — built for fast operational decisions.
                </div>
                <div class="scope-pill">
                    {scope_text} &nbsp;·&nbsp; {start_date} → {end_date}
                </div>
            </div></div></div>
    </div>
    """)

    # KPIs
    # -----------------------------------------------------------------------------

    total_arrivals = arrivals.arrival_quantity_qtl.sum() if not arrivals.empty else 0
    avg_modal = prices.modal_price.mean() if not prices.empty else 0
    valid_msp = prices[prices.msp.notna()].copy()
    below_count = int((valid_msp.modal_price < valid_msp.msp).sum()) if not valid_msp.empty else 0
    below_rate = below_count / len(valid_msp) * 100 if len(valid_msp) else 0

    if not transport.empty:
        threshold_df = transit_threshold()
        if not threshold_df.empty and "p90_transit_hours" in threshold_df.columns:
            p90 = float(threshold_df.p90_transit_hours.iloc[0])
        else:
            p90 = float(transport.transit_hours.quantile(.90))
        avg_transit = transport.transit_hours.mean()
        delay_rate = (transport.transit_hours.gt(p90).mean() * 100)
    else:
        p90 = avg_transit = delay_rate = 0

    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("Total arrivals", f"{total_arrivals:,.0f} Qtl")
    k2.metric("Avg modal price", f"₹{avg_modal:,.0f}")
    k3.metric("Below MSP", f"{below_rate:.1f}%")
    k4.metric("Avg transit", f"{avg_transit:.1f} h")
    k5.metric("Delay rate", f"{delay_rate:.1f}%")

    render_html('<div class="section-title">Executive signals</div>')
    render_html('<div class="section-subtitle">A fast operational read before drilling into the tabs.</div>')

    s1,s2,s3 = st.columns(3)
    with s1:
        title = "⚠️ Price pressure" if below_rate >= 40 else ("🟡 Price watch" if below_rate >= 20 else "🟢 Price relatively stable")
        render_html(textwrap.dedent(f"""
        <div class="signal"><div class="signal-title">{title}</div><div class="signal-value">{below_rate:.1f}% below MSP</div>
        <div class="signal-text">{below_count:,} of {len(valid_msp):,} valid price observations are below the available MSP.</div></div>
        """))
    with s2:
        title = "⚠️ Logistics pressure" if delay_rate >= 10 else ("🟡 Logistics watch" if delay_rate >= 5 else "🟢 Logistics relatively stable")
        render_html(textwrap.dedent(f"""
        <div class="signal"><div class="signal-title">{title}</div><div class="signal-value">{delay_rate:.1f}% delayed</div>
        <div class="signal-text">Transport records above the empirical P90 threshold of {p90:.1f} hours.</div></div>
        """))
    with s3:
        render_html(textwrap.dedent(f"""
        <div class="signal"><div class="signal-title">📊 Analytical coverage</div><div class="signal-value">{len(arrivals):,} arrival rows</div>
        <div class="signal-text">{len(prices):,} price rows and {len(transport):,} valid transport rows are in scope.</div></div>
        """))

    st.divider()

    # -----------------------------------------------------------------------------
    # -----------------------------------------------------------------------------
    # DECISION COCKPIT
    # -----------------------------------------------------------------------------

    # Descriptive operational signals only. No fabricated composite risk score.

    def pct_change(current, previous):
        if previous is None or pd.isna(previous) or previous == 0:
            return None
        return (current - previous) / abs(previous) * 100


    # 7-day supply momentum.
    supply_latest = None
    supply_delta = None

    if not arrivals.empty:
        sd = (
            arrivals.groupby("date", as_index=False)
            .arrival_quantity_qtl.sum()
            .sort_values("date")
        )
        if len(sd) >= 14:
            latest = sd.tail(7).arrival_quantity_qtl.sum()
            previous = sd.iloc[-14:-7].arrival_quantity_qtl.sum()
            supply_latest = float(latest)
            supply_delta = pct_change(latest, previous)
        elif not sd.empty:
            supply_latest = float(sd.tail(7).arrival_quantity_qtl.sum())


    # Average price position relative to MSP.
    price_gap_pct = None
    if not valid_msp.empty:
        m = valid_msp.modal_price.mean()
        s = valid_msp.msp.mean()
        if s:
            price_gap_pct = (m - s) / s * 100


    # Slowest mandi in current transport scope.
    slowest_name = None
    slowest_hours = None

    if not transport.empty:
        slow = (
            transport.groupby(["mandi_name", "district"], as_index=False)
            .agg(avg_transit=("transit_hours", "mean"))
            .sort_values("avg_transit", ascending=False)
        )
        if not slow.empty:
            slowest_name = slow.iloc[0].mandi_name
            slowest_hours = float(slow.iloc[0].avg_transit)


    # Latest weather pulse within selected arrival window.
    weather_peak = None
    weather_day = None

    if not weather.empty:
        ww = weather.copy()
        ww["weather_date_ist"] = pd.to_datetime(ww.weather_date_ist)
        ww = ww[
            ww.weather_date_ist.dt.date.between(start_date, end_date)
        ].dropna(subset=["max_rainfall_mm"])

        if not ww.empty:
            wr = ww.sort_values("weather_date_ist").iloc[-1]
            weather_peak = float(wr.max_rainfall_mm)
            weather_day = wr.weather_date_ist.date()


    def momentum_text(value):
        if value is None:
            return "Not enough history for a 7-day comparison"
        return f"{value:+.1f}% vs previous 7 days"


    render_html(
        """
        <div class="section-ribbon">
            <span class="tag">Live decision signals</span>
            <span class="line"></span>
        </div>
        """,
    )

    render_html(
        f"""
        <div class="command-strip">

            <div class="command-card">
                <div class="command-label">Supply momentum</div>
                <div class="command-value">
                    {"N/A" if supply_latest is None else f"{supply_latest:,.0f} Qtl"}
                </div>
                <div class="command-delta">
                    {momentum_text(supply_delta)}
                </div>
                <div class="command-note">
                    Latest 7 available arrival days in the selected scope.
                </div>
            </div>

            <div class="command-card gold">
                <div class="command-label">Price position</div>
                <div class="command-value">
                    {"N/A" if price_gap_pct is None else f"{price_gap_pct:+.1f}%"}
                </div>
                <div class="command-delta warn">
                    {below_rate:.1f}% below MSP
                </div>
                <div class="command-note">
                    Average modal price relative to average available MSP.
                </div>
            </div>

            <div class="command-card blue">
                <div class="command-label">Logistics bottleneck</div>
                <div class="command-value">
                    {"N/A" if slowest_hours is None else f"{slowest_hours:.1f} h"}
                </div>
                <div class="command-delta neutral">
                    {slowest_name or "No valid mandi movement"}
                </div>
                <div class="command-note">
                    Highest average transit among mandis in scope.
                </div>
            </div>

            <div class="command-card violet">
                <div class="command-label">Weather pulse</div>
                <div class="command-value">
                    {"N/A" if weather_peak is None else f"{weather_peak:.1f} mm"}
                </div>
                <div class="command-delta neutral">
                    {weather_day or "No valid weather day"}
                </div>
                <div class="command-note">
                    Maximum valid sensor rainfall on the latest weather day.
                </div>
            </div>

        </div>
        """,
    )


    # -----------------------------------------------------------------------------
    # MANDI OPERATING LANDSCAPE
    # -----------------------------------------------------------------------------

    landscape = pd.DataFrame()

    if not arrivals.empty:
        landscape = (
            arrivals.groupby(
                ["mandi_id", "mandi_name", "district", "state"],
                as_index=False,
            )
            .agg(arrivals_qtl=("arrival_quantity_qtl", "sum"))
        )

        if not transport.empty:
            lt = (
                transport.groupby("mandi_id", as_index=False)
                .agg(avg_transit_hours=("transit_hours", "mean"))
            )
            landscape = landscape.merge(lt, on="mandi_id", how="left")

        if not prices.empty:
            lp = prices[prices.msp.notna()].copy()
            if not lp.empty:
                lp["below_msp"] = lp.modal_price < lp.msp
                lps = (
                    lp.groupby("mandi_id", as_index=False)
                    .agg(
                        below_msp_rate=("below_msp", "mean"),
                        price_observations=("below_msp", "size"),
                    )
                )
                lps["below_msp_rate"] *= 100
                landscape = landscape.merge(
                    lps, on="mandi_id", how="left"
                )

    if (
        not landscape.empty
        and {"avg_transit_hours", "below_msp_rate"}.issubset(landscape.columns)
    ):
        lp = landscape.dropna(
            subset=["avg_transit_hours", "below_msp_rate"]
        ).copy()

        if not lp.empty:
            render_html(
                """
                <div class="section-ribbon">
                    <span class="tag">Mandi operating landscape</span>
                    <span class="line"></span>
                </div>
                """,
            )

            st.caption(
                "A two-signal operating map: slower mandis move right; higher "
                "below-MSP pressure moves up. Bubble size represents arrival volume."
            )

            fig = px.scatter(
                lp,
                x="avg_transit_hours",
                y="below_msp_rate",
                size="arrivals_qtl",
                hover_name="mandi_name",
                hover_data={
                    "district": True,
                    "state": True,
                    "arrivals_qtl": ":,.0f",
                    "avg_transit_hours": ":.1f",
                    "below_msp_rate": ":.1f",
                    "price_observations": True,
                },
                labels={
                    "avg_transit_hours": "Average transit (hours)",
                    "below_msp_rate": "Below-MSP rate (%)",
                    "arrivals_qtl": "Arrival volume (Qtl)",
                },
            )

            fig.update_traces(
                marker=dict(
                    opacity=.80,
                    line=dict(width=1),
                )
            )

            chart(fig, 455)


    # -----------------------------------------------------------------------------
    # OPERATIONAL WATCHLIST
    # -----------------------------------------------------------------------------

    watchlist = pd.DataFrame()

    if (
        not landscape.empty
        and {"avg_transit_hours", "below_msp_rate"}.issubset(landscape.columns)
    ):
        med_transit = landscape.avg_transit_hours.median(skipna=True)
        med_pressure = landscape.below_msp_rate.median(skipna=True)

        if not pd.isna(med_transit) and not pd.isna(med_pressure):
            watchlist = landscape.dropna(
                subset=["avg_transit_hours", "below_msp_rate"]
            ).copy()

            watchlist = watchlist[
                watchlist.avg_transit_hours.gt(med_transit)
                & watchlist.below_msp_rate.gt(med_pressure)
            ].sort_values(
                ["below_msp_rate", "avg_transit_hours"],
                ascending=False,
            ).head(8)

    if not watchlist.empty:
        a, b = st.columns([1.35, 1])

        with a:
            render_html(
                """
                <div class="section-ribbon">
                    <span class="tag">Operational watchlist</span>
                    <span class="line"></span>
                </div>
                """,
            )

            st.caption(
                "Mandis above the filtered median on both transit time and "
                "below-MSP rate. This is a relative watchlist, not a risk score."
            )

            wd = watchlist[
                [
                    "mandi_name",
                    "district",
                    "arrivals_qtl",
                    "avg_transit_hours",
                    "below_msp_rate",
                ]
            ]

            st.dataframe(
                wd,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "mandi_name": "Mandi",
                    "district": "District",
                    "arrivals_qtl": st.column_config.NumberColumn(
                        "Arrivals (Qtl)", format="%,.0f"
                    ),
                    "avg_transit_hours": st.column_config.NumberColumn(
                        "Transit (h)", format="%.1f"
                    ),
                    "below_msp_rate": st.column_config.NumberColumn(
                        "Below MSP", format="%.1f%%"
                    ),
                },
            )

        with b:
            top_watch = watchlist.iloc[0]

            render_html(
                f"""
                <div class="watch-card">
                    <div class="command-label">Highest combined pressure</div>
                    <strong>{top_watch.mandi_name}</strong>
                    <div class="small">
                        {top_watch.district} ·
                        {top_watch.avg_transit_hours:.1f} h average transit ·
                        {top_watch.below_msp_rate:.1f}% below MSP.
                    </div>
                    <div class="watch-chip">ABOVE MEDIAN ON BOTH SIGNALS</div>
                </div>
                """,
            )




    # -----------------------------------------------------------------------------
    # ARRIVAL SHOCK RADAR — ADVANCED INSIGHT
    # -----------------------------------------------------------------------------

    render_html("""
    <div class="section-ribbon">
        <span class="tag">Advanced insight · arrival shock radar</span>
        <span class="line"></span>
    </div>
    <div class="section-title">Supply movement outside the recent baseline</div>
    <div class="section-subtitle">
        Compares recent average observed-day arrivals with the immediately preceding
        window. Coverage is shown explicitly so sparse records do not masquerade as anomalies.
    </div>
    """)

    try:
        shock = arrival_shock_by_mandi(window_days=30, min_observed_days=3)
    except Exception as exc:
        shock = pd.DataFrame()
        st.warning(f"Arrival shock analysis unavailable: {exc}")

    if selected_states and not shock.empty:
        shock = shock[shock["state"].isin(selected_states)]
    if selected_districts and not shock.empty:
        shock = shock[shock["district"].isin(selected_districts)]
    if selected_mandis and not shock.empty:
        shock = shock[shock["mandi_id"].isin(selected_mandis)]

    if not shock.empty:
        negative = shock[shock["shock_direction"] == "DROP"].sort_values("shock_pct")
        positive = shock[shock["shock_direction"] == "SURGE"].sort_values("shock_pct", ascending=False)
        top_abs = shock.sort_values("abs_shock_pct", ascending=False)
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Eligible mandis", f"{len(shock):,}")
        s2.metric("Arrival drops", f"{len(negative):,}")
        s3.metric("Arrival surges", f"{len(positive):,}")
        s4.metric("Largest movement", f"{top_abs.iloc[0]['shock_pct']:+.1f}%")

        left, right = st.columns([1.65, 1])
        with left:
            plot_df = shock.sort_values("shock_pct").head(15).copy()
            plot_df["signal"] = plot_df["shock_direction"].map({"DROP":"SUPPLY DROP", "SURGE":"SUPPLY SURGE", "STABLE":"WITHIN BASELINE"})
            fig = px.bar(
                plot_df,
                x="shock_pct",
                y="mandi_name",
                orientation="h",
                color="signal",
                hover_data={
                    "mandi_id": True,
                    "recent_avg_daily_qtl": ":,.1f",
                    "baseline_avg_daily_qtl": ":,.1f",
                    "shock_pct": ":+.1f",
                    "recent_observed_days": True,
                    "baseline_observed_days": True,
                    "coverage_pct": ":.0f",
                },
                labels={
                    "shock_pct": "Change in average observed-day arrivals (%)",
                    "mandi_name": "Mandi",
                    "signal": "Signal",
                },
                color_discrete_map={
                    "SUPPLY DROP": "#ff6f7d",
                    "SUPPLY SURGE": "#42e6a4",
                    "WITHIN BASELINE": "#8ea4b0",
                },
            )
            fig.add_vline(x=-20, line_dash="dash", opacity=.65)
            fig.add_vline(x=20, line_dash="dash", opacity=.65)
            fig.add_vline(x=0, line_dash="dot", opacity=.55)
            chart(fig, 470)

        with right:
            top = top_abs.iloc[0]
            direction_text = "drop" if top["shock_pct"] < 0 else "surge"
            render_html(f"""
            <div class="watch-card">
                <div class="command-label">Largest observed movement</div>
                <strong>{top['mandi_name']}</strong>
                <div class="small">{top['mandi_id']} · {top['shock_pct']:+.1f}% {direction_text}</div>
                <div class="small" style="margin-top:.7rem;">
                    Recent: <b>{top['recent_avg_daily_qtl']:,.0f} Qtl/day</b><br>
                    Baseline: <b>{top['baseline_avg_daily_qtl']:,.0f} Qtl/day</b><br>
                    Coverage: <b>{top['recent_observed_days'] + top['baseline_observed_days']} observed days</b>
                </div>
                <div class="watch-chip">{top['shock_confidence']} CONFIDENCE</div>
            </div>
            """)
            st.caption(
                "A drop/surge threshold of ±20% is a descriptive alert rule. "
                "The comparison is normalized by observed days and requires at least "
                "three observed days in each window."
            )

        # Action layer: translate signals into an operational next step.
        scoped_actions = actions.copy() if isinstance(actions, pd.DataFrame) else pd.DataFrame()
        if not scoped_actions.empty:
            if selected_states:
                scoped_actions = scoped_actions[scoped_actions["state"].isin(selected_states)]
            if selected_districts:
                scoped_actions = scoped_actions[scoped_actions["district"].isin(selected_districts)]
            if selected_mandis:
                scoped_actions = scoped_actions[scoped_actions["mandi_id"].isin(selected_mandis)]
            scoped_actions = scoped_actions[
                scoped_actions["action_priority"].astype(str).isin(["CRITICAL", "HIGH", "ELEVATED"])
            ].head(8)

        if not scoped_actions.empty:
            render_html("""
            <div class="section-ribbon" style="margin-top:1.4rem;">
                <span class="tag">Action engine</span>
                <span class="line"></span>
            </div>
            <div class="section-subtitle">
                Converts the existing explainable risk and arrival-shock signals into a ranked operational response.
            </div>
            """)
            action_view = scoped_actions[[
                "mandi_name", "action_priority", "operational_risk_score",
                "shock_pct", "recommended_action"
            ]].copy()
            st.dataframe(
                action_view,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "mandi_name": "Mandi",
                    "action_priority": "Priority",
                    "operational_risk_score": st.column_config.NumberColumn("Risk", format="%.1f"),
                    "shock_pct": st.column_config.NumberColumn("Arrival change", format="%+.1f%%"),
                    "recommended_action": "Recommended action",
                },
            )
    else:
        no_data(
            "Not enough repeated mandi-day observations to establish a coverage-aware arrival shock. "
            "The detector requires at least three observed days in both the recent and baseline windows."
        )


    # RISK COMMAND CENTER
    # -----------------------------------------------------------------------------

    render_html("""
    <div class="section-ribbon">
        <span class="tag">Risk command center</span>
        <span class="line"></span>
    </div>
    """)

    if system_risk:
        overall = system_risk.get("overall_risk_score")
        market_score = system_risk.get("market_system_score")
        logistics_score = system_risk.get("logistics_system_score")
        weather_score = system_risk.get("weather_system_score")

        r1, r2, r3, r4 = st.columns(4)

        r1.metric(
            "System priority",
            "N/A" if overall is None else f"{float(overall):.0f}/100",
            risk_status(overall),
        )
        r2.metric(
            "Market stress",
            "N/A" if market_score is None else f"{float(market_score):.0f}/100",
            risk_status(market_score),
        )
        r3.metric(
            "Logistics stress",
            "N/A" if logistics_score is None else f"{float(logistics_score):.0f}/100",
            risk_status(logistics_score),
        )
        r4.metric(
            "Weather stress",
            "N/A" if weather_score is None else f"{float(weather_score):.0f}/100",
            risk_status(weather_score),
        )

        st.caption(
            system_risk.get(
                "warning",
                "Scores are relative prioritization signals, not probabilities.",
            )
        )

    # Filter the risk table using the same scope as the rest of the dashboard.
    risk_scope = mandi_risk.copy()

    if not risk_scope.empty:
        if selected_states:
            risk_scope = risk_scope[
                risk_scope["state"].isin(selected_states)
            ]

        if selected_districts:
            risk_scope = risk_scope[
                risk_scope["district"].isin(selected_districts)
            ]

        if selected_mandis:
            risk_scope = risk_scope[
                risk_scope["mandi_id"].isin(selected_mandis)
            ]

    if not risk_scope.empty:
        render_html("""
        <div class="section-ribbon">
            <span class="tag">Priority mandis</span>
            <span class="line"></span>
        </div>
        """)

        top_risk = risk_scope.sort_values(
            "operational_risk_score",
            ascending=False,
        ).head(8).copy()

        left, right = st.columns([1.45, 1])

        with left:
            display = top_risk[
                [
                    "mandi_id",
                    "mandi_name",
                    "district",
                    "market_stress_score",
                    "logistics_stress_score",
                    "operational_risk_score",
                    "operational_risk",
                ]
            ].copy()

            display["status"] = display["operational_risk"].map(
                {
                    "HIGH": "🔴 HIGH",
                    "ELEVATED": "🟠 ELEVATED",
                    "WATCH": "🟡 WATCH",
                    "LOW": "🟢 LOW",
                }
            )

            st.dataframe(
                display[
                    [
                        "mandi_id",
                        "mandi_name",
                        "district",
                        "market_stress_score",
                        "logistics_stress_score",
                        "operational_risk_score",
                        "status",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "mandi_id": "ID",
                    "mandi_name": "Mandi",
                    "district": "District",
                    "market_stress_score": st.column_config.NumberColumn(
                        "Market", format="%.0f"
                    ),
                    "logistics_stress_score": st.column_config.NumberColumn(
                        "Logistics", format="%.0f"
                    ),
                    "operational_risk_score": st.column_config.NumberColumn(
                        "Priority", format="%.0f"
                    ),
                    "status": "Status",
                },
            )

        with right:
            top = top_risk.iloc[0]

            render_html(f"""
            <div class="watch-card">
                <div class="command-label">Highest priority in scope</div>
                <strong>{top["mandi_name"]}</strong>
                <div class="small">
                    {top["district"]} ·
                    Operational priority {top["operational_risk_score"]:.0f}/100 ·
                    {top["operational_risk"]}
                </div>
                <div class="small" style="margin-top:.7rem;">
                    <b>Market:</b> {top["market_reason"]}<br><br>
                    <b>Logistics:</b> {top["logistics_reason"]}
                </div>
                <div class="watch-chip">EXPLAINABLE PRIORITY</div>
            </div>
            """)

    else:
        st.caption(
            "No mandi risk observations match the current filters."
        )

    # -----------------------------------------------------------------------------
    # SUPPLY CHAIN STRESS MATRIX — SIGNATURE VISUAL
    # -----------------------------------------------------------------------------

    render_html("""
    <div class="section-ribbon">
        <span class="tag">Supply chain stress matrix</span>
        <span class="line"></span>
    </div>
    """)

    render_html("""
    <div class="section-title">
        Where is operational pressure concentrated?
    </div>
    <div class="section-subtitle">
        Mandis with both slower movement and stronger below-MSP pressure
        deserve the closest operational attention. Bubble size represents
        arrival volume.
    </div>
    """)

    if not landscape.empty and {
        "avg_transit_hours",
        "below_msp_rate",
        "arrivals_qtl",
    }.issubset(landscape.columns):

        matrix = landscape.dropna(
            subset=[
                "avg_transit_hours",
                "below_msp_rate",
                "arrivals_qtl",
            ]
        ).copy()

        if not matrix.empty:

            # ---------------------------------------------------------
            # Relative thresholds
            # ---------------------------------------------------------

            transit_median = matrix["avg_transit_hours"].median()
            price_median = matrix["below_msp_rate"].median()

            def quadrant(row):
                slow = row["avg_transit_hours"] >= transit_median
                pressure = row["below_msp_rate"] >= price_median

                if slow and pressure:
                    return "CRITICAL — High pressure + slow logistics"
                elif pressure:
                    return "MARKET — High price pressure"
                elif slow:
                    return "LOGISTICS — Slow movement"
                else:
                    return "STABLE — Lower relative pressure"

            matrix["operating_zone"] = matrix.apply(
                quadrant,
                axis=1,
            )

            # ---------------------------------------------------------
            # Matrix
            # ---------------------------------------------------------

            fig = px.scatter(
                matrix,
                x="avg_transit_hours",
                y="below_msp_rate",
                size="arrivals_qtl",
                color="operating_zone",
                hover_name="mandi_name",
                hover_data={
                    "mandi_id": True,
                    "district": True,
                    "state": True,
                    "arrivals_qtl": ":,.0f",
                    "avg_transit_hours": ":.1f",
                    "below_msp_rate": ":.1f",
                    "operating_zone": True,
                },
                color_discrete_map={
                    "CRITICAL — High pressure + slow logistics": "#E47767",
                    "MARKET — High price pressure": "#E8B65A",
                    "LOGISTICS — Slow movement": "#6BC9B4",
                    "STABLE — Lower relative pressure": "#72D572",
                },
                labels={
                    "avg_transit_hours": "Average transit (hours)",
                    "below_msp_rate": "Below-MSP rate (%)",
                    "arrivals_qtl": "Arrival volume (Qtl)",
                    "operating_zone": "Operating zone",
                },
            )

            # Median lines create the four operating zones
            fig.add_vline(
                x=transit_median,
                line_dash="dash",
                line_color="#8EA4B0",
                opacity=.7,
            )

            fig.add_hline(
                y=price_median,
                line_dash="dash",
                line_color="#8EA4B0",
                opacity=.7,
            )

            # Add annotations
            fig.add_annotation(
                x=matrix["avg_transit_hours"].max(),
                y=matrix["below_msp_rate"].max(),
                text="CRITICAL",
                showarrow=False,
                font=dict(
                    size=11,
                    color="#E47767",
                ),
                xanchor="right",
                yanchor="top",
            )

            fig.add_annotation(
                x=matrix["avg_transit_hours"].min(),
                y=matrix["below_msp_rate"].max(),
                text="MARKET PRESSURE",
                showarrow=False,
                font=dict(
                    size=10,
                    color="#E8B65A",
                ),
                xanchor="left",
                yanchor="top",
            )

            fig.add_annotation(
                x=matrix["avg_transit_hours"].max(),
                y=matrix["below_msp_rate"].min(),
                text="LOGISTICS PRESSURE",
                showarrow=False,
                font=dict(
                    size=10,
                    color="#6BC9B4",
                ),
                xanchor="right",
                yanchor="bottom",
            )

            fig.add_annotation(
                x=matrix["avg_transit_hours"].min(),
                y=matrix["below_msp_rate"].min(),
                text="RELATIVELY STABLE",
                showarrow=False,
                font=dict(
                    size=10,
                    color="#72D572",
                ),
                xanchor="left",
                yanchor="bottom",
            )

            chart(fig, 560)

            # ---------------------------------------------------------
            # Decision takeaway
            # ---------------------------------------------------------

            critical = matrix[
                matrix["operating_zone"]
                == "CRITICAL — High pressure + slow logistics"
            ].sort_values(
                [
                    "below_msp_rate",
                    "avg_transit_hours",
                ],
                ascending=False,
            )

            if not critical.empty:

                top = critical.iloc[0]

                render_html(f"""
                <div class="signal" style="margin-top:.7rem;">
                    <div class="signal-title">
                        🎯 Decision takeaway
                    </div>

                    <div class="signal-text"
                         style="font-size:.84rem;color:#c5d1ca;">

                        <b>{top["mandi_name"]}</b> is the strongest
                        combined-pressure observation in the matrix,
                        with {top["below_msp_rate"]:.1f}% of available
                        price observations below MSP and
                        {top["avg_transit_hours"]:.1f} hours average transit.

                        This matrix is a relative prioritization view,
                        not a causal or predictive risk model.
                    </div>
                </div>
                """)

            st.caption(
                f"Dashed lines show the filtered medians: "
                f"{transit_median:.1f}h transit and "
                f"{price_median:.1f}% below-MSP rate."
            )

        else:
            no_data(
                "Not enough valid mandi observations to construct the stress matrix."
            )

    else:
        no_data(
            "Stress matrix requires arrival, transit and price-pressure signals."
        )


    # -----------------------------------------------------------------------------
    # RISK RANKING — DECISION VIEW
    # -----------------------------------------------------------------------------

    if not mandi_risk.empty:

        render_html("""
        <div class="section-ribbon">
            <span class="tag">Priority ranking</span>
            <span class="line"></span>
        </div>
        """)

        risk_rank = mandi_risk.copy()

        # Apply the same geographic filters as the dashboard
        if selected_states and "state" in risk_rank.columns:
            risk_rank = risk_rank[
                risk_rank["state"].isin(selected_states)
            ]

        if selected_districts and "district" in risk_rank.columns:
            risk_rank = risk_rank[
                risk_rank["district"].isin(selected_districts)
            ]

        if selected_mandis and "mandi_id" in risk_rank.columns:
            risk_rank = risk_rank[
                risk_rank["mandi_id"].isin(selected_mandis)
            ]

        risk_rank = risk_rank.sort_values(
            "operational_risk_score",
            ascending=False,
        ).head(10)

        if not risk_rank.empty:

            fig = px.bar(
                risk_rank.sort_values("operational_risk_score"),
                x="operational_risk_score",
                y="mandi_name",
                orientation="h",
                hover_data=[
                    c
                    for c in [
                        "mandi_id",
                        "district",
                        "market_stress_score",
                        "logistics_stress_score",
                        "operational_risk",
                    ]
                    if c in risk_rank.columns
                ],
                labels={
                    "operational_risk_score": "Operational priority",
                    "mandi_name": "Mandi",
                },
                color="operational_risk_score",
                color_continuous_scale=[
                    "#72D572",
                    "#E8B65A",
                    "#E47767",
                ],
            )

            fig.add_vline(
                x=80,
                line_dash="dash",
                line_color="#E47767",
                opacity=.75,
            )

            chart(fig, 470)

            st.caption(
                "Operational priority combines market and logistics stress. "
                "Scores are prioritization signals, not probabilities."
            )



def _set_agriquery_question(question):
    st.session_state["agq_pending_question"] = question
    st.session_state["agq_run_after_input"] = True


def _clear_agriquery():
    st.session_state["agq_clear_requested"] = True
    st.session_state["agriquery_run"] = False


with tab_agriquery:
    # -----------------------------------------------------------------------------
    # AGRIQUERY — NATURAL LANGUAGE INTELLIGENCE
    # -----------------------------------------------------------------------------

    render_html("""
    <div class="agq-shell">
        <div class="agq-kicker">Agentic Graph AI · Live analytical data</div>
        <div class="agq-title">Ask AgriQuery</div>
        <div class="agq-copy">
            Ask in plain language. AgriQuery resolves entities, selects the analytical
            path, retrieves grounded evidence, chooses a visual and explains the result.
        </div>
        <div class="agq-flow">QUESTION <span>→</span> INTENT <span>→</span> DATA <span>→</span> VISUAL <span>→</span> DECISION</div>
    </div>
    """)

    render_html("""
    <div class="agq-examples-title">Try a command</div>
    """)
    example_questions = [
        "Top 5 mandis by arrivals",
        "Which mandis are below MSP?",
        "What is the risk for MANDI047?",
        "Which mandis have both high price pressure and slow logistics?",
        "Show wheat arrivals for the last 30 days",
    ]

    ex_cols = st.columns(5)
    for idx, example in enumerate(example_questions):
        with ex_cols[idx]:
            st.button(
                example,
                key=f"agq_example_{idx}",
                use_container_width=True,
                help="Load this question into AgriQuery",
                on_click=_set_agriquery_question,
                args=(example,),
            )

    render_html("""
    <div class="agq-command-row">
        <div class="agq-mini"><div class="k">Ask</div><div class="v">Natural-language question</div></div>
        <div class="agq-mini"><div class="k">Grounding</div><div class="v">Validated DuckDB</div></div>
        <div class="agq-mini"><div class="k">Output</div><div class="v">Visual + explanation</div></div>
    </div>
    """)

    if "agriquery_input" not in st.session_state:
        st.session_state["agriquery_input"] = ""
    if "agriquery_run" not in st.session_state:
        st.session_state["agriquery_run"] = False
    if st.session_state.pop("agq_clear_requested", False):
        st.session_state["agriquery_input"] = ""
    pending = st.session_state.pop("agq_pending_question", None)
    if pending is not None:
        st.session_state["agriquery_input"] = pending
        st.session_state["agriquery_run"] = True

    query = st.text_area(
        "Ask AgriQuery",
        placeholder="Ask anything about arrivals, prices, MSP, mandis, logistics, weather or risk…",
        key="agriquery_input",
        height=112,
        label_visibility="collapsed",
    )

    run_col, clear_col, hint_col = st.columns([1.15, .85, 3.2])
    with run_col:
        run_clicked = st.button("▶ Run analysis", key="agq_run", use_container_width=True)
    with clear_col:
        st.button("Clear", key="agq_clear", use_container_width=True, on_click=_clear_agriquery)
    with hint_col:
        st.caption("Validated DuckDB · visual + explanation · no fabricated observations")

    if run_clicked:
        st.session_state["agriquery_run"] = True

    should_run = bool(query.strip()) and bool(st.session_state.get("agriquery_run", False))

    if should_run:

        with st.spinner("AgriQuery is analyzing the data..."):

            try:
                agent_result = run_question(query)

                result_df = agent_result["data"]
                intent = agent_result["intent"]
                chart_type = agent_result["chart_type"]
                summary = agent_result["summary"]

                # ---------------------------------------------------------
                # AGENT RESPONSE
                # ---------------------------------------------------------

                st.markdown("### AgriQuery result")

                r1, r2 = st.columns([1, 3])

                with r1:
                    st.metric(
                        "Detected intent",
                        intent.replace("_", " ").title(),
                    )

                with r2:
                    st.metric(
                        "Recommended view",
                        chart_type.title(),
                    )

                # ---------------------------------------------------------
                # TEXT EXPLANATION
                # ---------------------------------------------------------

                render_html(f"""
                <div class="signal" style="margin:.5rem 0 1rem;">
                    <div class="signal-title">🧠 Agent explanation</div>
                    <div class="signal-text"
                         style="font-size:.86rem;color:#c5d1ca;">
                        {summary}
                    </div>
                </div>
                """)

                # ---------------------------------------------------------
                # INTELLIGENT AGENT VISUALIZATION
                # ---------------------------------------------------------

                if result_df.empty:

                    no_data("AgriQuery returned no matching observations.")

                # =========================================================
                # SIGNATURE VIEW: SUPPLY-CHAIN STRESS MATRIX
                # =========================================================

                elif chart_type == "stress_matrix":

                    matrix = result_df.copy()

                    required = {
                        "avg_transit_hours",
                        "below_msp_rate",
                        "arrivals_qtl",
                    }

                    if required.issubset(matrix.columns):

                        matrix = matrix.dropna(
                            subset=[
                                "avg_transit_hours",
                                "below_msp_rate",
                                "arrivals_qtl",
                            ]
                        ).copy()

                        if matrix.empty:
                            no_data(
                                "Not enough valid observations to build the stress matrix."
                            )
                        else:

                            transit_median = float(
                                matrix["avg_transit_hours"].median()
                            )
                            price_median = float(
                                matrix["below_msp_rate"].median()
                            )

                            def classify_zone(row):
                                slow = (
                                    row["avg_transit_hours"]
                                    >= transit_median
                                )
                                pressure = (
                                    row["below_msp_rate"]
                                    >= price_median
                                )

                                if slow and pressure:
                                    return "CRITICAL"
                                if pressure:
                                    return "MARKET PRESSURE"
                                if slow:
                                    return "LOGISTICS PRESSURE"
                                return "RELATIVELY STABLE"

                            matrix["operating_zone"] = matrix.apply(
                                classify_zone,
                                axis=1,
                            )

                            # Relative combined-pressure index used only to
                            # identify the strongest observation in this view.
                            matrix["pressure_index"] = (
                                matrix["below_msp_rate"]
                                / max(price_median, 0.0001)
                                +
                                matrix["avg_transit_hours"]
                                / max(transit_median, 0.0001)
                            )

                            fig = px.scatter(
                                matrix,
                                x="avg_transit_hours",
                                y="below_msp_rate",
                                size="arrivals_qtl",
                                color="operating_zone",
                                hover_name=(
                                    "mandi_name"
                                    if "mandi_name" in matrix.columns
                                    else "mandi_id"
                                ),
                                hover_data={
                                    "mandi_id": True,
                                    "district": (
                                        True
                                        if "district" in matrix.columns
                                        else False
                                    ),
                                    "state": (
                                        True
                                        if "state" in matrix.columns
                                        else False
                                    ),
                                    "arrivals_qtl": ":,.0f",
                                    "below_msp_rate": ":.1f",
                                    "avg_transit_hours": ":.1f",
                                    "delay_rate": (
                                        ":.1f"
                                        if "delay_rate" in matrix.columns
                                        else False
                                    ),
                                    "operating_zone": True,
                                    "pressure_index": False,
                                },
                                color_discrete_map={
                                    "CRITICAL": "#E47767",
                                    "MARKET PRESSURE": "#E8B65A",
                                    "LOGISTICS PRESSURE": "#6BC9B4",
                                    "RELATIVELY STABLE": "#72D572",
                                },
                                labels={
                                    "avg_transit_hours": "Average transit (hours)",
                                    "below_msp_rate": "Below-MSP rate (%)",
                                    "arrivals_qtl": "Arrival volume (Qtl)",
                                    "operating_zone": "Operating zone",
                                },
                            )

                            fig.add_vline(
                                x=transit_median,
                                line_dash="dash",
                                line_color="#8EA4B0",
                                opacity=.75,
                            )

                            fig.add_hline(
                                y=price_median,
                                line_dash="dash",
                                line_color="#8EA4B0",
                                opacity=.75,
                            )

                            x_min = float(matrix["avg_transit_hours"].min())
                            x_max = float(matrix["avg_transit_hours"].max())
                            y_min = float(matrix["below_msp_rate"].min())
                            y_max = float(matrix["below_msp_rate"].max())

                            fig.add_annotation(
                                x=x_max,
                                y=y_max,
                                text="<b>CRITICAL</b>",
                                showarrow=False,
                                font=dict(size=11, color="#E47767"),
                                xanchor="right",
                                yanchor="top",
                            )

                            fig.add_annotation(
                                x=x_min,
                                y=y_max,
                                text="<b>MARKET PRESSURE</b>",
                                showarrow=False,
                                font=dict(size=10, color="#E8B65A"),
                                xanchor="left",
                                yanchor="top",
                            )

                            fig.add_annotation(
                                x=x_max,
                                y=y_min,
                                text="<b>LOGISTICS PRESSURE</b>",
                                showarrow=False,
                                font=dict(size=10, color="#6BC9B4"),
                                xanchor="right",
                                yanchor="bottom",
                            )

                            fig.add_annotation(
                                x=x_min,
                                y=y_min,
                                text="<b>RELATIVELY STABLE</b>",
                                showarrow=False,
                                font=dict(size=10, color="#72D572"),
                                xanchor="left",
                                yanchor="bottom",
                            )

                            fig.update_traces(
                                marker=dict(
                                    opacity=.84,
                                    line=dict(width=1),
                                )
                            )

                            chart(fig, 560)

                            m1, m2, m3 = st.columns(3)

                            m1.metric(
                                "Price-pressure median",
                                f"{price_median:.1f}%",
                                "below MSP",
                            )

                            m2.metric(
                                "Transit median",
                                f"{transit_median:.1f} h",
                                "average transit",
                            )

                            m3.metric(
                                "Combined-pressure mandis",
                                f"{len(matrix[matrix['operating_zone'] == 'CRITICAL']):,}",
                                "above both medians",
                            )

                            critical = matrix[
                                matrix["operating_zone"] == "CRITICAL"
                            ]

                            if not critical.empty:

                                top = critical.sort_values(
                                    "pressure_index",
                                    ascending=False,
                                ).iloc[0]

                                top_name = top.get(
                                    "mandi_name",
                                    top.get("mandi_id", "Selected mandi"),
                                )

                                render_html(f"""
                                <div class="signal" style="margin-top:.7rem;">
                                    <div class="signal-title">
                                        🎯 Decision takeaway
                                    </div>
                                    <div class="signal-text"
                                         style="font-size:.84rem;color:#c5d1ca;">
                                        <b>{top_name}</b> is the strongest
                                        combined-pressure observation in this
                                        filtered view, with
                                        <b>{float(top["below_msp_rate"]):.1f}%</b>
                                        of available price observations below MSP
                                        and
                                        <b>{float(top["avg_transit_hours"]):.1f}h</b>
                                        average transit.
                                        <br><br>
                                        This is a <b>relative prioritization view</b>
                                        using filtered medians, not a probability,
                                        forecast, or causal model.
                                    </div>
                                </div>
                                """)

                            st.caption(
                                f"Dashed lines show the filtered medians: "
                                f"{transit_median:.1f}h transit and "
                                f"{price_median:.1f}% below-MSP rate. "
                                "Bubble size represents arrival volume."
                            )

                    else:

                        no_data(
                            "Stress matrix requires arrival volume, transit time "
                            "and below-MSP pressure."
                        )

                # =========================================================
                # PRICE VIEW: MODAL PRICE VS MSP
                # =========================================================

                elif chart_type == "price_comparison":

                    price_df = result_df.copy()

                    modal_col = next(
                        (
                            c
                            for c in [
                                "avg_modal_price",
                                "modal_price",
                            ]
                            if c in price_df.columns
                        ),
                        None,
                    )

                    msp_col = next(
                        (
                            c
                            for c in [
                                "avg_msp",
                                "msp",
                            ]
                            if c in price_df.columns
                        ),
                        None,
                    )

                    if modal_col and msp_col:

                        row = price_df.iloc[0]
                        modal = float(row[modal_col])
                        msp = float(row[msp_col])
                        gap = modal - msp

                        crop_name = str(
                            row.get(
                                "crop_name",
                                row.get("crop", "Selected crop"),
                            )
                        ).title()

                        render_html(f"""
                        <div class="section-title">
                            {crop_name} — Market Position vs MSP
                        </div>
                        <div class="section-subtitle">
                            Average modal price compared with the applicable
                            minimum support price.
                        </div>
                        """)

                        price_plot = pd.DataFrame(
                            {
                                "Metric": ["Modal Price", "MSP"],
                                "Price": [modal, msp],
                            }
                        )

                        fig = go.Figure(
                            go.Bar(
                                x=price_plot["Metric"],
                                y=price_plot["Price"],
                                text=[
                                    f"₹{modal:,.0f}",
                                    f"₹{msp:,.0f}",
                                ],
                                textposition="outside",
                                hovertemplate=(
                                    "%{x}<br>₹%{y:,.2f}"
                                    "<extra></extra>"
                                ),
                            )
                        )

                        fig.update_layout(
                            height=400,
                            yaxis_title="Price (₹)",
                            xaxis_title="",
                            showlegend=False,
                        )

                        chart(fig, 400)

                        p1, p2, p3 = st.columns(3)

                        p1.metric(
                            "Modal price",
                            f"₹{modal:,.0f}",
                        )

                        p2.metric(
                            "MSP",
                            f"₹{msp:,.0f}",
                        )

                        p3.metric(
                            "Gap vs MSP",
                            f"₹{gap:+,.0f}",
                        )

                        below = row.get("below_msp_rate")

                        if below is not None and pd.notna(below):

                            render_html(f"""
                            <div class="signal" style="margin-top:.7rem;">
                                <div class="signal-title">
                                    🎯 Price signal
                                </div>
                                <div class="signal-text"
                                     style="font-size:.84rem;color:#c5d1ca;">
                                    <b>{float(below):.1f}%</b> of available
                                    {crop_name.lower()} price observations
                                    are below MSP.
                                    The average modal price is
                                    <b>{"above" if gap >= 0 else "below"}</b>
                                    MSP by <b>₹{abs(gap):,.0f}</b>.
                                </div>
                            </div>
                            """)

                    else:

                        st.dataframe(
                            price_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                # =========================================================
                # ARRIVALS + MSP REFERENCE VIEW
                # =========================================================

                elif chart_type == "line_msp":

                    trend = result_df.copy()
                    date_col = next(
                        (c for c in ["arrival_date", "date"] if c in trend.columns),
                        None,
                    )

                    if date_col and "arrivals_qtl" in trend.columns:
                        trend[date_col] = pd.to_datetime(trend[date_col], errors="coerce")
                        trend["arrivals_qtl"] = pd.to_numeric(trend["arrivals_qtl"], errors="coerce")
                        if "avg_msp" in trend.columns:
                            trend["avg_msp"] = pd.to_numeric(trend["avg_msp"], errors="coerce")
                        trend = trend.dropna(subset=[date_col, "arrivals_qtl"]).sort_values(date_col)

                        if not trend.empty:
                            fig = go.Figure()

                            fig.add_trace(
                                go.Scatter(
                                    x=trend[date_col],
                                    y=trend["arrivals_qtl"],
                                    mode="lines+markers",
                                    name="Daily arrivals",
                                    line=dict(width=3),
                                    marker=dict(size=7),
                                )
                            )

                            if "avg_msp" in trend.columns and trend["avg_msp"].notna().any():
                                # MSP is a price reference, so keep it on a separate axis.
                                fig.add_trace(
                                    go.Scatter(
                                        x=trend[date_col],
                                        y=trend["avg_msp"],
                                        mode="lines",
                                        name="MSP reference",
                                        line=dict(width=2, dash="dash"),
                                        yaxis="y2",
                                    )
                                )

                            fig.update_layout(
                                title="Wheat arrivals vs MSP reference",
                                xaxis=dict(title="Date"),
                                yaxis=dict(
                                    title="Daily arrivals (Qtl)",
                                    rangemode="tozero",
                                ),
                                yaxis2=dict(
                                    title="MSP (₹/Qtl)",
                                    overlaying="y",
                                    side="right",
                                    rangemode="tozero",
                                ),
                                hovermode="x unified",
                                legend=dict(orientation="h", y=1.08, x=0),
                            )

                            chart(fig, 500)

                            latest = trend.iloc[-1]
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Days with arrival data", f"{len(trend):,}")
                            c2.metric("Latest arrivals", f"{float(latest['arrivals_qtl']):,.2f} Qtl")
                            if "avg_msp" in trend.columns and trend["avg_msp"].notna().any():
                                msp_value = float(trend["avg_msp"].dropna().iloc[-1])
                                c3.metric("MSP reference", f"₹{msp_value:,.0f}/Qtl")

                            st.caption(
                                "The solid line is observed daily arrival volume. "
                                "The dashed line is the available MSP reference; missing daily price observations are not fabricated."
                            )
                        else:
                            no_data("No valid arrival observations were available for this trend.")
                    else:
                        st.dataframe(result_df, use_container_width=True, hide_index=True)

                # =========================================================
                # BAR VIEW
                # =========================================================

                elif chart_type == "bar":

                    numeric_cols = result_df.select_dtypes(
                        include="number"
                    ).columns.tolist()

                    if numeric_cols:

                        preferred_values = [
                            "arrivals_qtl",
                            "below_msp_rate",
                            "avg_modal_price",
                            "avg_msp",
                            "operational_risk_score",
                        ]

                        value_col = next(
                            (
                                c
                                for c in preferred_values
                                if c in numeric_cols
                            ),
                            numeric_cols[-1],
                        )

                        label_candidates = [
                            "mandi_name",
                            "crop_name",
                            "crop",
                            "mandi_id",
                            "district",
                        ]

                        label_col = next(
                            (
                                c
                                for c in label_candidates
                                if c in result_df.columns
                            ),
                            None,
                        )

                        if label_col:

                            plot_df = result_df.copy()

                            fig = px.bar(
                                plot_df,
                                x=value_col,
                                y=label_col,
                                orientation="h",
                                hover_data=[
                                    c
                                    for c in result_df.columns
                                    if c not in [value_col, label_col]
                                ],
                                labels={
                                    value_col: value_col.replace(
                                        "_", " "
                                    ).title(),
                                    label_col: label_col.replace(
                                        "_", " "
                                    ).title(),
                                },
                            )

                            chart(
                                fig,
                                max(
                                    420,
                                    min(
                                        720,
                                        45 * len(plot_df),
                                    ),
                                ),
                            )

                        else:

                            st.dataframe(
                                result_df,
                                use_container_width=True,
                                hide_index=True,
                            )

                    else:

                        st.dataframe(
                            result_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                # =========================================================
                # LINE / TREND VIEW
                # =========================================================

                elif chart_type == "line":

                    date_col = next(
                        (
                            col
                            for col in [
                                "arrival_date",
                                "date",
                                "price_date",
                            ]
                            if col in result_df.columns
                        ),
                        None,
                    )

                    numeric_cols = result_df.select_dtypes(
                        include="number"
                    ).columns.tolist()

                    if date_col and numeric_cols:

                        preferred_values = [
                            "arrivals_qtl",
                            "modal_price",
                            "avg_modal_price",
                        ]

                        value_col = next(
                            (
                                c
                                for c in preferred_values
                                if c in numeric_cols
                            ),
                            numeric_cols[-1],
                        )

                        plot_df = result_df.copy()
                        plot_df[date_col] = pd.to_datetime(
                            plot_df[date_col]
                        )

                        fig = px.line(
                            plot_df,
                            x=date_col,
                            y=value_col,
                            markers=True,
                            labels={
                                date_col: "Date",
                                value_col: value_col.replace(
                                    "_", " "
                                ).title(),
                            },
                        )

                        chart(fig, 460)

                    else:

                        st.dataframe(
                            result_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                # =========================================================
                # RISK INDICATOR
                # =========================================================

                elif chart_type == "indicator":

                    if "operational_risk_score" in result_df.columns:

                        row = result_df.iloc[0]

                        score = float(
                            row["operational_risk_score"]
                        )

                        risk = str(
                            row.get(
                                "operational_risk",
                                "N/A",
                            )
                        )

                        c1, c2, c3 = st.columns(3)

                        c1.metric(
                            "Operational priority",
                            f"{score:.0f}/100",
                            risk,
                        )

                        if "market_stress_score" in result_df.columns:

                            c2.metric(
                                "Market stress",
                                f"{float(row['market_stress_score']):.0f}/100",
                                str(
                                    row.get(
                                        "market_stress",
                                        "",
                                    )
                                ),
                            )

                        if "logistics_stress_score" in result_df.columns:

                            c3.metric(
                                "Logistics stress",
                                f"{float(row['logistics_stress_score']):.0f}/100",
                                str(
                                    row.get(
                                        "logistics_stress",
                                        "",
                                    )
                                ),
                            )

                        evidence_cols = [
                            "mandi_id",
                            "mandi_name",
                            "district",
                            "below_msp_rate",
                            "avg_msp_gap_pct",
                            "avg_transit_hours",
                            "delay_rate",
                            "p90_threshold_hours",
                        ]

                        evidence_cols = [
                            c
                            for c in evidence_cols
                            if c in result_df.columns
                        ]

                        if evidence_cols:

                            st.markdown("**Risk evidence**")

                            st.dataframe(
                                result_df[evidence_cols],
                                use_container_width=True,
                                hide_index=True,
                            )

                    else:

                        st.dataframe(
                            result_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                # =========================================================
                # FALLBACK
                # =========================================================

                else:

                    st.dataframe(
                        result_df,
                        use_container_width=True,
                        hide_index=True,
                    )

                # ---------------------------------------------------------
                # RAW DATA / SQL
                # ---------------------------------------------------------

                with st.expander("View agent evidence · SQL + returned data"):

                    st.write(
                        f"**Intent:** `{intent}`"
                    )

                    st.write(
                        f"**Chart type:** `{chart_type}`"
                    )

                    if agent_result.get("sql"):

                        st.code(
                            agent_result["sql"],
                            language="sql",
                        )

                    st.dataframe(
                        result_df,
                        use_container_width=True,
                        hide_index=True,
                    )

            except Exception as exc:

                st.error(
                    f"AgriQuery could not process this question: {exc}"
                )




with tab_supply:
    st.subheader("Supply intelligence")
    if arrivals.empty:
        no_data("No valid arrival records match the current filters.")
    else:
        daily = arrivals.groupby("date", as_index=False).arrival_quantity_qtl.sum().sort_values("date")
        crop = arrivals.groupby("crop", as_index=False).arrival_quantity_qtl.sum().sort_values("arrival_quantity_qtl", ascending=False)
        a,b = st.columns([1.65,1])
        with a:
            st.markdown("**Arrival volume over time**")
            fig = px.area(daily, x="date", y="arrival_quantity_qtl", labels={"date":"Date","arrival_quantity_qtl":"Arrivals (Qtl)"})
            fig.update_traces(line_width=2)
            chart(fig, 410)
        with b:
            st.markdown("**Crop mix**")
            fig = px.bar(crop.sort_values("arrival_quantity_qtl"), x="arrival_quantity_qtl", y="crop", orientation="h", color="crop", color_discrete_sequence=["#72D572","#A8C686","#6BC9B4","#E8B65A","#B19A78","#8AB6A8"], labels={"arrival_quantity_qtl":"Arrivals (Qtl)","crop":"Crop"})
            chart(fig, 410)

        st.markdown("**Mandi supply concentration**")
        mandi = arrivals.groupby(["mandi_id","mandi_name","district","state"], as_index=False).arrival_quantity_qtl.sum().sort_values("arrival_quantity_qtl", ascending=False).head(15).sort_values("arrival_quantity_qtl")
        fig = px.bar(mandi, x="arrival_quantity_qtl", y="mandi_name", orientation="h", hover_data=["district","state"], labels={"arrival_quantity_qtl":"Arrivals (Qtl)","mandi_name":"Mandi"})
        chart(fig, 500)

with tab_price:
    st.subheader("Price intelligence")
    if prices.empty:
        no_data("No price records match the current filters.")
    else:
        by_crop = prices.groupby("crop", as_index=False).agg(modal_price=("modal_price","mean"),msp=("msp","mean"))
        by_crop["gap"] = by_crop.modal_price - by_crop.msp
        long = by_crop.melt(id_vars="crop", value_vars=["modal_price","msp"], var_name="price_type", value_name="price")
        long.price_type = long.price_type.replace({"modal_price":"Modal price","msp":"MSP"})
        a,b = st.columns([1.55,1])
        with a:
            st.markdown("**Modal price vs MSP**")
            fig = px.bar(long, x="crop", y="price", color="price_type", barmode="group", color_discrete_map={"Modal price":"#72D572","MSP":"#E8B65A"}, labels={"crop":"Crop","price":"Price (₹)","price_type":""})
            chart(fig, 420)
        with b:
            st.markdown("**Average price gap**")
            fig = px.bar(by_crop.sort_values("gap"), x="gap", y="crop", orientation="h", labels={"gap":"Modal price − MSP (₹)","crop":"Crop"})
            fig.add_vline(x=0, line_dash="dash")
            chart(fig, 420)

        st.markdown("**Where is price pressure concentrated?**")
        p = prices[prices.msp.notna()].copy()
        if p.empty:
            no_data("No observations with an available MSP are in scope.")
        else:
            p["below_msp"] = p.modal_price < p.msp
            summary = p.groupby("crop", as_index=False).agg(observations=("below_msp","size"),below_msp=("below_msp","sum"))
            summary["below_msp_rate"] = summary.below_msp / summary.observations * 100
            fig = px.bar(summary.sort_values("below_msp_rate"), x="below_msp_rate", y="crop", orientation="h", text="below_msp_rate", hover_data=["below_msp","observations"], labels={"below_msp_rate":"Below-MSP rate (%)","crop":"Crop"})
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            chart(fig, 410)
            st.caption("Below-MSP rate is a price-pressure indicator, not automatically a market crash.")

with tab_logistics:
    st.subheader("Supply-chain intelligence")
    if transport.empty:
        no_data("No valid transport records match the current filters.")
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Average",f"{transport.transit_hours.mean():.1f} h")
        c2.metric("Median",f"{transport.transit_hours.median():.1f} h")
        c3.metric("P90",f"{p90:.1f} h")
        c4.metric("Delay rate",f"{delay_rate:.1f}%")
        st.divider()
        a,b = st.columns([1.35,1])
        with a:
            st.markdown("**Transit-time distribution**")
            fig = px.histogram(transport, x="transit_hours", nbins=25, labels={"transit_hours":"Transit time (hours)"})
            fig.add_vline(x=p90, line_dash="dash", annotation_text=f"P90 = {p90:.1f}h")
            chart(fig, 420)
        with b:
            st.markdown("**Slowest mandi movements**")
            mt = transport.groupby(["mandi_name","district"],as_index=False).agg(avg_transit_hours=("transit_hours","mean"),trips=("transit_hours","count")).sort_values("avg_transit_hours",ascending=False).head(10).sort_values("avg_transit_hours")
            fig = px.bar(mt,x="avg_transit_hours",y="mandi_name",orientation="h",hover_data=["district","trips"],labels={"avg_transit_hours":"Average transit (h)","mandi_name":"Mandi"})
            chart(fig,420)
        st.info(f"Delay = transit above the empirical P90 threshold of {p90:.1f} hours. This is a dataset-derived analytical benchmark, not an external SLA.")

        # Destination warehouse and route performance are derived directly from
        # the transport records. The source contains trip records but no
        # shipment quantity, so trip count is reported as activity rather than Qtl.
        if "destination_warehouse" in transport.columns:
            st.divider()
            st.markdown("**Destination warehouse performance**")
            wh = (transport.dropna(subset=["destination_warehouse"])
                  .assign(destination_warehouse=lambda d: d.destination_warehouse.astype(str).str.strip())
                  .query("destination_warehouse != ''")
                  .groupby("destination_warehouse", as_index=False)
                  .agg(trips=("transit_hours", "count"),
                       avg_transit_hours=("transit_hours", "mean"),
                       median_transit_hours=("transit_hours", "median"),
                       avg_distance_km=("distance_km", "mean")))
            if not wh.empty:
                wh["delay_rate_pct"] = (transport.assign(
                    destination_warehouse=transport.destination_warehouse.astype(str).str.strip())
                    .groupby("destination_warehouse").transit_hours
                    .apply(lambda x: x.gt(p90).mean() * 100).reindex(wh.destination_warehouse).to_numpy())
                wh = wh.sort_values(["delay_rate_pct", "avg_transit_hours"], ascending=False)
                a,b = st.columns([1.15, 1])
                with a:
                    fig = px.bar(wh.sort_values("avg_transit_hours"), x="avg_transit_hours", y="destination_warehouse", orientation="h",
                                 hover_data=["trips", "median_transit_hours", "delay_rate_pct", "avg_distance_km"],
                                 labels={"avg_transit_hours":"Average transit (h)", "destination_warehouse":"Destination warehouse"})
                    chart(fig, 380)
                with b:
                    st.dataframe(wh, use_container_width=True, hide_index=True,
                                 column_config={
                                     "destination_warehouse":"Warehouse",
                                     "trips":st.column_config.NumberColumn("Trips", format="%d"),
                                     "avg_transit_hours":st.column_config.NumberColumn("Avg transit (h)", format="%.1f"),
                                     "median_transit_hours":st.column_config.NumberColumn("Median (h)", format="%.1f"),
                                     "avg_distance_km":st.column_config.NumberColumn("Avg distance (km)", format="%.1f"),
                                     "delay_rate_pct":st.column_config.NumberColumn("Delay rate", format="%.1f%%"),
                                 })

                st.markdown("**Mandi → warehouse routes with highest delay frequency**")
                route = (transport.dropna(subset=["destination_warehouse", "mandi_id"])
                         .assign(destination_warehouse=lambda d: d.destination_warehouse.astype(str).str.strip())
                         .groupby(["mandi_id", "mandi_name", "district", "destination_warehouse"], as_index=False)
                         .agg(trips=("transit_hours", "count"), avg_transit_hours=("transit_hours", "mean"),
                              delayed_trips=("transit_hours", lambda x: int(x.gt(p90).sum()))))
                route = route[route.trips >= 10].copy()
                if not route.empty:
                    route["delay_rate_pct"] = route.delayed_trips / route.trips * 100
                    st.dataframe(route.sort_values(["delay_rate_pct", "delayed_trips"], ascending=False).head(15),
                                 use_container_width=True, hide_index=True,
                                 column_config={
                                     "mandi_id":"Mandi ID", "mandi_name":"Mandi", "district":"District",
                                     "destination_warehouse":"Warehouse", "trips":st.column_config.NumberColumn("Trips", format="%d"),
                                     "avg_transit_hours":st.column_config.NumberColumn("Avg transit (h)", format="%.1f"),
                                     "delayed_trips":st.column_config.NumberColumn("Delayed trips", format="%d"),
                                     "delay_rate_pct":st.column_config.NumberColumn("Delay rate", format="%.1f%%"),
                                 })
                st.caption("Trip activity is not shipment tonnage; the transport source contains no quantity field. Delay uses the dataset-derived P90 benchmark.")

with tab_weather:
    st.subheader("Weather signals")
    relationship = arrivals.groupby("date",as_index=False).arrival_quantity_qtl.sum()
    relationship["date"] = pd.to_datetime(relationship.date)
    w = weather.copy()
    w["weather_date_ist"] = pd.to_datetime(w.weather_date_ist)
    relationship = relationship.merge(w,left_on="date",right_on="weather_date_ist",how="inner")
    if relationship.empty:
        no_data("There is not enough overlapping weather and arrival data for the current scope.")
    else:
        a,b = st.columns(2)
        with a:
            st.markdown("**Arrivals and rainfall over time**")
            fig = go.Figure(go.Scatter(x=relationship.date,y=relationship.arrival_quantity_qtl,name="Arrivals",mode="lines",line=dict(width=2)))
            fig.update_layout(xaxis_title="Date",yaxis_title="Arrivals (Qtl)",hovermode="x unified")
            chart(fig,420)
        with b:
            st.markdown("**Rainfall vs arrival volume**")
            scatter = relationship.dropna(subset=["avg_rainfall_mm","arrival_quantity_qtl"])
            if scatter.empty:
                no_data("No valid rainfall observations overlap this period.")
            else:
                fig = px.scatter(scatter,x="avg_rainfall_mm",y="arrival_quantity_qtl",hover_data=["date"],labels={"avg_rainfall_mm":"Average rainfall (mm/sensor)","arrival_quantity_qtl":"Arrivals (Qtl)"})
                chart(fig,420)
        corr = relationship[["arrival_quantity_qtl","avg_temperature_c","avg_rainfall_mm"]].dropna()
        rainfall_corr = corr.arrival_quantity_qtl.corr(corr.avg_rainfall_mm) if len(corr)>=2 else None
        temp_corr = corr.arrival_quantity_qtl.corr(corr.avg_temperature_c) if len(corr)>=2 else None
        r1,r2,r3 = st.columns(3)
        r1.metric("Rainfall ↔ arrivals", "N/A" if rainfall_corr is None else f"{rainfall_corr:.3f}")
        r2.metric("Temperature ↔ arrivals", "N/A" if temp_corr is None else f"{temp_corr:.3f}")
        r3.metric("Overlapping days",f"{len(relationship):,}")
        st.caption("Correlations describe statistical association in the supplied synthetic data; they do not establish causation. District weather attribution uses the tracked synthetic sensor→district mapping permitted by the dataset notes; it is not source geography.")

        # District weather attribution uses the explicit competition assumption.
        # UNKNOWN sensors stay outside district-level attribution.
        district_weather = q(f"""
            WITH daily AS (
                SELECT district, weather_date_ist,
                       AVG(temperature_c) avg_temperature_c,
                       AVG(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) avg_rainfall_mm,
                       MAX(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) peak_rainfall_mm,
                       COUNT(DISTINCT CASE WHEN rainfall_status='VALID' THEN sensor_id END) reporting_sensors
                FROM weather
                WHERE district IS NOT NULL AND weather_date_ist IS NOT NULL
                GROUP BY district, weather_date_ist
            )
            SELECT district, ROUND(AVG(avg_temperature_c),2) avg_temperature_c,
                   ROUND(SUM(avg_rainfall_mm),2) cumulative_avg_rainfall_mm,
                   ROUND(MAX(peak_rainfall_mm),2) peak_rainfall_mm,
                   SUM(reporting_sensors) sensor_day_reports, COUNT(*) observed_days
            FROM daily GROUP BY district ORDER BY cumulative_avg_rainfall_mm DESC
        """)
        if not district_weather.empty:
            st.divider()
            st.markdown("**District weather attribution**")
            st.caption("Synthetic sensor→district mapping per dataset notes. Multiple sensors may map to a district; UNKNOWN sensors are excluded. Cumulative rainfall = sum of daily district-average rainfall.")
            st.dataframe(district_weather, use_container_width=True, hide_index=True,
                         column_config={
                             "district":"District",
                             "avg_temperature_c":st.column_config.NumberColumn("Avg temperature (°C)", format="%.1f"),
                             "cumulative_avg_rainfall_mm":st.column_config.NumberColumn("Cumulative avg rainfall (mm)", format="%.1f"),
                             "peak_rainfall_mm":st.column_config.NumberColumn("Peak rainfall (mm)", format="%.1f"),
                             "sensor_day_reports":st.column_config.NumberColumn("Sensor-day reports", format="%d"),
                             "observed_days":st.column_config.NumberColumn("Observed days", format="%d"),
                         })

with tab_mandi:
    st.subheader("Mandi explorer")
    if arrivals.empty:
        no_data("No mandi records match the current filters.")
    else:
        ms = arrivals.groupby(["mandi_id","mandi_name","district","state"],as_index=False).agg(arrivals_qtl=("arrival_quantity_qtl","sum"))
        if not transport.empty:
            ts = transport.groupby("mandi_id",as_index=False).agg(avg_transit_hours=("transit_hours","mean"),transport_records=("transit_hours","count"))
            ms = ms.merge(ts,on="mandi_id",how="left")
        else:
            ms["avg_transit_hours"] = pd.NA
            ms["transport_records"] = pd.NA
        if not prices.empty:
            pm = prices[prices.msp.notna()].copy()
            if not pm.empty:
                pm["below_msp"] = pm.modal_price < pm.msp
                ps = pm.groupby("mandi_id",as_index=False).agg(below_msp_rate=("below_msp","mean"))
                ps.below_msp_rate *= 100
                ms = ms.merge(ps,on="mandi_id",how="left")
        if "below_msp_rate" not in ms:
            ms["below_msp_rate"] = pd.NA
        ms = ms.sort_values("arrivals_qtl",ascending=False)
        st.dataframe(ms,use_container_width=True,hide_index=True,column_config={
            "mandi_id":"Mandi ID","mandi_name":"Mandi","district":"District","state":"State",
            "arrivals_qtl":st.column_config.NumberColumn("Arrivals (Qtl)",format="%,.0f"),
            "avg_transit_hours":st.column_config.NumberColumn("Avg transit (h)",format="%.1f"),
            "transport_records":st.column_config.NumberColumn("Transport records",format="%d"),
            "below_msp_rate":st.column_config.NumberColumn("Below-MSP rate",format="%.1f%%"),
        })
        st.divider()
        metric_label = st.selectbox("Compare mandis by",["Arrival volume","Average transit","Below-MSP rate"])
        metric = {"Arrival volume":"arrivals_qtl","Average transit":"avg_transit_hours","Below-MSP rate":"below_msp_rate"}[metric_label]
        cd = ms[["mandi_name",metric]].dropna().sort_values(metric).tail(15)
        if cd.empty:
            no_data("The selected metric has no valid observations for this scope.")
        else:
            fig = px.bar(cd,x=metric,y="mandi_name",orientation="h",labels={metric:metric_label,"mandi_name":"Mandi"})
            chart(fig,500)

# -----------------------------------------------------------------------------

# RISK DEEP DIVE
# -----------------------------------------------------------------------------

with tab_risk:
    st.subheader("Explainable risk intelligence")

    if mandi_risk.empty:
        no_data(
            "Risk engine returned no mandi observations. "
            "Run `python src\\risk_engine.py` to validate the risk layer."
        )
    else:
        scoped = mandi_risk.copy()

        if selected_states:
            scoped = scoped[scoped["state"].isin(selected_states)]
        if selected_districts:
            scoped = scoped[scoped["district"].isin(selected_districts)]
        if selected_mandis:
            scoped = scoped[scoped["mandi_id"].isin(selected_mandis)]

        if scoped.empty:
            no_data("No risk observations match the selected mandi scope.")
        else:
            scoped = scoped.sort_values(
                "operational_risk_score",
                ascending=False,
            )

            # Streamlit may call format_func with option values in a way that
            # makes dataframe-based positional lookup brittle. Build a stable
            # ID -> label mapping once, then use a direct dictionary lookup.
            scoped = scoped.dropna(subset=["mandi_id"]).copy()
            scoped["mandi_id"] = scoped["mandi_id"].astype(str)
            scoped = scoped.drop_duplicates(subset=["mandi_id"], keep="first")
            mandi_labels = {
                str(r["mandi_id"]): f"{r['mandi_name']} · {r['mandi_id']}"
                for _, r in scoped.iterrows()
            }
            mandi_options = list(mandi_labels.keys())

            selected_id = st.selectbox(
                "Inspect mandi",
                mandi_options,
                format_func=lambda x: mandi_labels.get(
                    str(x), str(x)
                ),
            )

            row = scoped[
                scoped["mandi_id"].eq(str(selected_id))
            ].iloc[0]

            a, b, c = st.columns(3)
            a.metric(
                "Operational priority",
                f"{row['operational_risk_score']:.0f}/100",
                str(row["operational_risk"]),
            )
            b.metric(
                "Market stress",
                f"{row['market_stress_score']:.0f}/100",
                str(row["market_stress"]),
            )
            c.metric(
                "Logistics stress",
                f"{row['logistics_stress_score']:.0f}/100",
                str(row["logistics_stress"]),
            )

            render_html(f"""
            <div class="watch-card" style="margin-top:1rem;">
                <div class="command-label">Why this mandi is prioritized</div>
                <strong>{row["mandi_name"]}</strong>
                <div class="small">
                    {row["district"]} · {row["state"]}
                </div>
                <div class="small" style="margin-top:.7rem;">
                    <b>Market:</b> {row["market_reason"]}<br><br>
                    <b>Logistics:</b> {row["logistics_reason"]}
                </div>
                <div class="watch-chip">
                    RELATIVE TO OBSERVED MANDI POPULATION
                </div>
            </div>
            """)

            component_df = pd.DataFrame(
                {
                    "component": ["Market", "Logistics"],
                    "score": [
                        float(row["market_stress_score"]),
                        float(row["logistics_stress_score"]),
                    ],
                }
            )

            fig = px.bar(
                component_df,
                x="component",
                y="score",
                text="score",
                labels={
                    "component": "",
                    "score": "Relative stress score",
                },
            )
            fig.update_traces(
                texttemplate="%{text:.0f}",
                textposition="outside",
            )
            fig.update_yaxes(range=[0, 100])
            chart(fig, 360)

            st.caption(
                "Relative percentile-based prioritization; not a probability "
                "of loss or a forecast."
            )

# DATA TRUST
# -----------------------------------------------------------------------------

st.divider()
with st.expander("🛡️ Data trust & analytical notes"):
    st.markdown("""
### Standardization
- Crop names → canonical crop categories
- Mandi IDs → canonical `MANDI###`
- Arrival quantities → Quintals
- Distances → Kilometers
- Currency strings → numeric prices
- Weather timestamps → UTC + IST
- Temperature → Celsius
- Rainfall → millimeters
- Vehicle registrations → normalized representation

### Quality decisions
Invalid negative transit records are excluded from transit performance calculations rather than silently converted. Negative rainfall observations are retained for auditability but excluded from valid rainfall analytics. Missing values are tracked explicitly.

### Weather geography assumption
The weather workbook contains no district field. The competition notes explicitly permit a 1:1 sensor-location assumption for district mapping. DatOps therefore uses a tracked deterministic sensor→district mapping: each known sensor is assigned to one district, multiple sensors may share a district, and UNKNOWN sensors remain unattributed. This is a synthetic analytical assumption, not source geography.

### Price limitation
Below-MSP observations indicate price pressure. They are not automatically labeled as market crashes.

### Transit / warehouse note
The transport source includes `destination_warehouse`, so warehouse and mandi→warehouse route performance are reported directly. The source does not include shipment quantity, so warehouse "volume" is represented only as inbound trip activity, never as Qtl.

### Synthetic-data note
The competition dataset is synthetic/educational. Source metadata is treated as supplied rather than silently corrected when geography or naming appears unusual.
""")

render_html("<div class='footer'>DatOps · Mandi Intelligence · Decision analytics</div>")
