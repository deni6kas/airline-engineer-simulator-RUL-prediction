"""PADII RUL Engineer - interactive ML-demo simulator (Streamlit).

A pixel-art, top-down airport where the player is PADII's chief engineer.
Every decision (fly / maintain) is driven by PRECOMPUTED RUL predictions and
turned into money, so the value (and the cost of error) of the ML model is
visible in dollars. No model is trained at runtime.
"""
from __future__ import annotations

import base64
from io import BytesIO

import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

from game import config, data_loader, economics, scene, state, charts
from game.styles import CSS

st.set_page_config(page_title=config.GAME_TITLE, page_icon="✈", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
state.init_state()

SENSOR_ICONS = {
    "egt": "🌡️", "core_speed": "⚙️",
    "hpc_pressure": "📈", "corr_core_speed": "🔄",
}
BADGE = {config.STATUS_SAFE: "safe", config.STATUS_WARNING: "warn",
         config.STATUS_CRITICAL: "crit"}
ADVICE = {
    config.STATUS_SAFE: ("safe", "Двигатель в норме. Можно продолжать полёты и "
                                  "выжимать ресурс."),
    config.STATUS_WARNING: ("warn", "Рекомендуется постановка в график ТО. "
                                     "Риск растёт."),
    config.STATUS_CRITICAL: ("crit", "Критический износ! Отправьте борт на ТО, "
                                      "иначе вероятна авария."),
}


def money(v: int) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,}"


@st.cache_data(show_spinner=False)
def _sprite_b64(name: str, max_side: int = 150) -> str:
    im = Image.open(config.ASSETS_DIR / name).convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- HUD
def render_hud():
    s = st.session_state
    sel = s["selected_aircraft"] or "—"
    variant = config.MODEL_VARIANTS[s["mode"]]["label"]
    xp_pct = int(100 * s["xp"] / s["xp_next"])
    st.markdown(f"""
    <div class="hud">
      <div class="hud-cell">
        <span class="hud-k">Engineer LVL {s['level']}</span>
        <div class="xpbar"><span style="width:{xp_pct}%"></span></div>
      </div>
      <div class="hud-title">PADII <span class="star">★</span> AIRLINES</div>
      <div style="display:flex; gap:26px;">
        <div class="hud-cell"><span class="hud-k">Model</span>
          <span class="hud-v">{variant}</span></div>
        <div class="hud-cell"><span class="hud-k">Selected</span>
          <span class="hud-v">{sel}</span></div>
        <div class="hud-cell"><span class="hud-k">Company Budget</span>
          <span class="hud-v hud-budget">{money(s['budget'])}</span></div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------- LOBBY
def render_lobby():
    st.markdown(f"""
    <div class="lobby-hero">
      <div class="t">PADII <span class="star">★</span> RUL ENGINEER</div>
      <div class="s">{config.GAME_TAGLINE}</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
        <div class="panel" style="margin-top:8px">
          <p style="color:var(--ink);font-size:14px;line-height:1.6">
          Вы — главный инженер авиакомпании. Модель прогнозирования
          <b>RUL</b> (остаточного ресурса двигателя) <b>уже обучена</b> на данных
          NASA C-MAPSS. В игре используются только <b>заранее посчитанные
          прогнозы</b> — ничего не обучается, каждый цикл обновляется мгновенно.<br><br>
          Решайте: пустить борт в рейс (<b>+$5,000</b>) или отправить на ТО
          (<b>−$50,000</b>). Ошибётесь — авария обойдётся в <b>−$5,000,000</b>.
          </p>
        </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><h4>Выбор модели</h4>", unsafe_allow_html=True)
        mode = st.radio(
            "mode", options=list(config.MODEL_VARIANTS.keys()),
            format_func=lambda k: config.MODEL_VARIANTS[k]["label"],
            label_visibility="collapsed", horizontal=True,
        )
        st.caption(config.MODEL_VARIANTS[mode]["desc"])
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        k1, k2 = st.columns(2)
        k1.markdown(f"<div class='kpi'><div class='k'>Стартовый бюджет</div>"
                    f"<div class='v' style='color:var(--gold)'>"
                    f"{money(config.START_BUDGET)}</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='kpi'><div class='k'>Флот PADII</div>"
                    f"<div class='v'>{len(data_loader.fleet_ids())} бортов</div></div>",
                    unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶  START CAMPAIGN", type="primary", use_container_width=True):
            state.start_campaign(mode)
            st.rerun()


# ---------------------------------------------------------------- FLEET PANEL
def render_fleet_panel(fleet):
    st.markdown("<div class='panel'><h4>Aircraft Fleet</h4>", unsafe_allow_html=True)
    meta = data_loader.load_metadata().set_index("aircraft_id")
    for i, aid in enumerate(fleet):
        s = state.ac_state(aid)
        ep = s["status"]
        if ep == "active":
            stt = state.status(aid)
            rul = f"{state.predicted_rul(aid):.0f}"
        elif ep == "maintained":
            stt, rul = config.STATUS_SAFE, "TO"
        else:
            stt, rul = config.STATUS_CRITICAL, "✕"
        col = config.COL[{"Safe": "safe", "Warning": "warning",
                          "Critical": "critical"}[stt]]
        sub = f"{meta.loc[aid,'model_name']} · {meta.loc[aid,'engine_model']}"
        state_txt = {"active": "ACTIVE", "maintained": "MAINTENANCE",
                     "crashed": "FAILED"}[ep]
        sel = "sel" if aid == st.session_state["selected_aircraft"] else ""
        st.markdown(f"""
        <div class="fleet-card {sel}">
          <div class="fleet-row">
            <img class="thumb" src="data:image/png;base64,{_sprite_b64('small_plane.png')}"/>
            <div class="fleet-info">
              <div class="fleet-top">
                <span class="fleet-id">{aid}</span>
                <span class="fleet-rul" style="color:{col}">{rul}</span>
              </div>
              <div class="fleet-sub">{sub}</div>
              <div class="fleet-sub"><span class="dot" style="background:{col}"></span>
                {state_txt}</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
        if st.button(f"Открыть борт {aid}", key=f"sel_{aid}",
                     use_container_width=True):
            st.session_state["selected_aircraft"] = aid
            st.session_state["sensor_mode"] = "grid"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- AIRPORT MAP
def render_map(fleet):
    status_map, ep_map = {}, {}
    for aid in fleet:
        ep_map[aid] = state.ac_state(aid)["status"]
        status_map[aid] = state.status(aid)
    img, hitboxes = scene.render_airport(
        fleet, st.session_state["selected_aircraft"], status_map, ep_map)

    val = streamlit_image_coordinates(img, key="airport_map")
    if val is not None and val.get("x") is not None:
        # the component reports click + displayed image width; rescale clicks
        # back into native scene coordinates so hit-testing is scale-proof.
        disp_w = val.get("width") or config.SCENE_W
        scale = config.SCENE_W / disp_w
        click = (round(val["x"] * scale), round(val["y"] * scale))
        if click != st.session_state.get("_last_click"):
            st.session_state["_last_click"] = click
            hit = scene.hit_test(hitboxes, click[0], click[1])
            if hit and hit != st.session_state["selected_aircraft"]:
                st.session_state["selected_aircraft"] = hit
                st.session_state["sensor_mode"] = "grid"
                st.rerun()
    st.markdown("<div class='legend'>Кликни по самолёту на карте или в списке справа · "
                "Статус: <b class='s'>Safe</b> RUL&gt;20 · "
                "<b class='w'>Warning</b> 5–20 · <b class='c'>Critical</b> &lt;5</div>",
                unsafe_allow_html=True)


# ---------------------------------------------------------------- CONSOLE
def render_console(aid):
    s = state.ac_state(aid)
    meta = data_loader.load_metadata().set_index("aircraft_id").loc[aid]
    done = s["episode_done"]
    pred = state.predicted_rul(aid)
    stt = state.status(aid)
    health = int(min(100, max(0, pred / 1.4)))

    head = (f"ENGINE TELEMETRY — {aid} — {meta['engine_model']} "
            f"({meta['engine_id']})")
    st.markdown(f"<div class='panel'><h4>{head}</h4>", unsafe_allow_html=True)

    left, mid, right = st.columns([1.15, 2.1, 1.25])

    # --- left: metrics + advice
    with left:
        m1, m2 = st.columns(2)
        m1.markdown(f"<div class='metric'><div class='k'>Current Cycle</div>"
                    f"<div class='v'>{s['cycle']}</div></div>", unsafe_allow_html=True)
        rcol = config.COL[{"Safe": "safe", "Warning": "warning",
                           "Critical": "critical"}[stt]]
        m2.markdown(f"<div class='metric'><div class='k'>Predicted RUL</div>"
                    f"<div class='v big' style='color:{rcol}'>{pred:.0f}</div>"
                    f"<div class='k'>cycles</div></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='margin:8px 0'><span class='badge {BADGE[stt]}'>"
                    f"{stt.upper()}</span> &nbsp;"
                    f"<span class='fleet-sub'>Health {health}%</span></div>",
                    unsafe_allow_html=True)
        acls, atxt = ADVICE[stt]
        st.markdown(f"<div class='advice {acls}'><b>System Advice</b><br>{atxt}</div>",
                    unsafe_allow_html=True)

    # --- middle: RUL chart
    with mid:
        pred_df = data_loader.prediction_series(aid, st.session_state["mode"], s["cycle"])
        fig = charts.rul_chart(pred_df, reveal_truth=done)
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False}, key=f"rul_{aid}")

    # --- right: sensors (grid OR detail) + action center
    with right:
        render_sensor_area(aid)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        render_action_center(aid, done)

    st.markdown("</div>", unsafe_allow_html=True)


def render_sensor_area(aid):
    s = state.ac_state(aid)
    catalog = data_loader.load_sensor_catalog()
    keys = list(catalog.keys())

    if st.session_state["sensor_mode"] == "detail" and st.session_state["selected_sensor"]:
        key = st.session_state["selected_sensor"]
        if st.button("◀ Back", key="sensor_back"):
            st.session_state["sensor_mode"] = "grid"
            st.rerun()
        df = data_loader.sensor_series(aid, key, s["cycle"])
        fig = charts.sensor_chart(df, catalog[key]["label"], height=150)
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False}, key=f"sens_{aid}_{key}")
    else:
        st.markdown("<div class='sensor-zone' style='font-size:10px;color:var(--dim);"
                    "text-transform:uppercase'>Sensors</div>", unsafe_allow_html=True)
        cols = st.columns(2)
        for i, key in enumerate(keys):
            with cols[i % 2]:
                if st.button(f"{SENSOR_ICONS.get(key,'•')}\n{catalog[key]['label']}",
                             key=f"sensor_{key}", use_container_width=True):
                    st.session_state["selected_sensor"] = key
                    st.session_state["sensor_mode"] = "detail"
                    st.rerun()


def render_action_center(aid, done):
    st.markdown("<div style='font-size:10px;color:var(--dim);text-transform:uppercase'>"
                "Action Center</div>", unsafe_allow_html=True)
    if done:
        st.info("Эпизод по этому борту завершён. Выберите другой самолёт.")
        return

    st.markdown("<span id='flight-anchor'></span>", unsafe_allow_html=True)
    if st.button(f"✈  CONTINUE FLIGHT  +{money(config.FLIGHT_REVENUE)[1:]}",
                 type="primary", use_container_width=True, key="continue_flight"):
        economics.continue_flight(aid)
        st.rerun()

    st.markdown("<span id='maint-anchor'></span>", unsafe_allow_html=True)
    if st.button(f"🔧  SEND TO MAINTENANCE  −$50,000",
                 use_container_width=True, key="maintenance"):
        economics.send_to_maintenance(aid)
        st.rerun()

    st.markdown("<div class='fleet-sub' style='margin-top:6px'>Следующий рейс "
                "уменьшит истинный ресурс на 1 цикл.</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- REPORT
def render_report():
    rep = st.session_state.get("report")
    if not rep:
        return
    cls = rep["result"]
    rows = (f"<b>Aircraft:</b> {rep['aircraft_id']} &nbsp;·&nbsp; "
            f"<b>Final cycle:</b> {rep['final_cycle']}<br>"
            f"<b>Predicted RUL (на момент решения):</b> {rep['predicted_rul']}<br>"
            f"<b>True RUL (раскрыт):</b> {rep['true_rul']}<br>"
            f"<b>Финансовый итог:</b> {money(rep['profit'])}")
    if rep["wasted_revenue"]:
        rows += (f"<br><b>Потеряно выручки:</b> ~{money(-rep['wasted_revenue'])[1:]} "
                 f"({rep['true_rul']} рейсов × $5,000)")
    st.markdown(f"""
    <div class="report {cls}">
      <h3>{'⚠ ' if cls=='crash' else ''}{rep['title']}</h3>
      <p style="color:var(--ink);font-size:14px;line-height:1.6">{rep['text']}</p>
      <p style="color:var(--dim);font-size:13px;line-height:1.7">{rows}</p>
    </div>""", unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("✓ Понятно", type="primary"):
        st.session_state["report"] = None
        st.rerun()
    if c2.button("📊 Итоги кампании"):
        st.session_state["report"] = None
        st.session_state["screen"] = "summary"
        st.rerun()


# ---------------------------------------------------------------- SUMMARY
def render_summary():
    s = st.session_state
    stats = s["stats"]
    errs = stats["errors"]
    mae = sum(errs) / len(errs) if errs else 0.0
    profit = s["budget"] - config.START_BUDGET

    st.markdown("<div class='lobby-hero'><div class='t'>CAMPAIGN SUMMARY</div></div>",
                unsafe_allow_html=True)
    cols = st.columns(5)
    kpis = [
        ("Итоговый бюджет", money(s["budget"]), "var(--gold)"),
        ("Прибыль/убыток", money(profit), "var(--safe)" if profit >= 0 else "var(--crit)"),
        ("Рейсы", str(stats["flights"]), "var(--ink)"),
        ("ТО", str(stats["maintenances"]), "var(--ink)"),
        ("Аварии", str(stats["crashes"]),
         "var(--crit)" if stats["crashes"] else "var(--safe)"),
    ]
    for c, (k, v, col) in zip(cols, kpis):
        c.markdown(f"<div class='kpi'><div class='k'>{k}</div>"
                   f"<div class='v' style='color:{col}'>{v}</div></div>",
                   unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"""
        <div class='panel'><h4>Что показала демонстрация</h4>
        <p style="color:var(--ink);font-size:14px;line-height:1.7">
        • Модель <b>{config.MODEL_VARIANTS[s['mode']]['label']}</b> давала прогноз RUL,
          средняя ошибка на момент решений — <b>{mae:.1f} цикла</b>.<br>
        • Каждый лишний рейс приносил +$5,000, поэтому <b>раннее ТО</b> снижало прибыль.<br>
        • <b>Позднее</b> решение могло привести к аварии (−$5,000,000) — это и есть
          цена ошибки модели в деньгах.<br>
        • Более осторожная <b>Safety-Aware</b> модель занижает RUL и уменьшает риск
          аварий ценой части выручки.
        </p></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='panel'><h4>Сравнение моделей</h4>"
                    "<p class='fleet-sub' style='line-height:1.7'>"
                    "Сыграйте кампанию обоими вариантами модели и сравните "
                    "итоговый бюджет и число аварий — это наглядно показывает "
                    "бизнес-ценность более безопасной модели.</p></div>",
                    unsafe_allow_html=True)
        if st.button("◀ Назад к аэропорту", use_container_width=True):
            s["screen"] = "airport"
            st.rerun()
        if st.button("🔄 Новая кампания", type="primary", use_container_width=True):
            s["screen"] = "lobby"
            st.rerun()


# ---------------------------------------------------------------- ROUTER
def render_airport_screen():
    render_hud()
    render_report()
    fleet = list(data_loader.fleet_ids())
    top = st.columns([3, 1])
    with top[0]:
        render_map(fleet)
    with top[1]:
        render_fleet_panel(fleet)

    aid = st.session_state["selected_aircraft"]
    if aid:
        render_console(aid)

    st.markdown("<br>", unsafe_allow_html=True)
    cc = st.columns([3, 1])
    with cc[1]:
        if st.button("📊 Завершить и посмотреть итоги", use_container_width=True):
            st.session_state["screen"] = "summary"
            st.rerun()


def main():
    screen = st.session_state["screen"]
    if screen == "lobby":
        render_lobby()
    elif screen == "summary":
        render_summary()
    else:
        render_airport_screen()


main()
