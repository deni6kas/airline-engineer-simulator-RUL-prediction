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
def _display_name(aircraft_id: str | None) -> str:
    if not aircraft_id:
        return "—"
    return config.aircraft_display_name(aircraft_id)


ADVICE = {
    config.STATUS_SAFE: ("safe", "Двигатель в норме. Можно продолжать полёты и "
                                  "выжимать ресурс."),
    config.STATUS_WARNING: ("warn", "Рекомендуется постановка в график ТО. "
                                     "Риск растёт."),
    config.STATUS_CRITICAL: ("crit", "Критический износ! Отправьте борт на ТО, "
                                      "иначе вероятна авария."),
}


def is_revealed(aid: str, kind: str) -> bool:
    key = "revealed_rul" if kind == "rul" else "revealed_advice"
    return bool(st.session_state.get(key, {}).get(aid))


def money(v: int) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,}"


def start_campaign(mode: str) -> None:
    st.session_state["tutorial_prompt"] = False
    st.session_state["pending_mode"] = None
    state.start_campaign(mode)


def clear_notice() -> None:
    st.session_state["notice"] = None
    state.resume_timer()


def close_report() -> None:
    st.session_state["report"] = None
    state.resume_timer()


def report_to_summary() -> None:
    st.session_state["report"] = None
    state.resume_timer()
    st.session_state["screen"] = "summary"


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


def _fleet_card_sprite(aircraft_id: str) -> str:
    sprites = config.AIRCRAFT_SPRITES.get(aircraft_id, config.DEFAULT_PLANE_SPRITES)
    return sprites["card"]


@st.cache_data(show_spinner=False, max_entries=128)
def _rul_figure(aid: str, variant: str, cycle: int, reveal: bool):
    pred_df = data_loader.prediction_series(aid, variant, cycle)
    return charts.rul_chart(pred_df, reveal_truth=reveal, height=330)


@st.cache_data(show_spinner=False, max_entries=128)
def _sensor_figure(aid: str, sensor_key: str, cycle: int):
    df = data_loader.sensor_series(aid, sensor_key, cycle).tail(
        config.SENSOR_WINDOW_CYCLES)
    label = data_loader.load_sensor_catalog()[sensor_key]["label"]
    return charts.sensor_chart(df, label, window=config.SENSOR_WINDOW_CYCLES,
                               height=380)


def render_notice():
    notice = st.session_state.get("notice")
    if not notice:
        return
    state.pause_timer()
    st.markdown(f"""
    <div class="notice-overlay">
      <div class="notice-toast">
        <b>Уведомление</b><br>{notice}
      </div>
    </div>""", unsafe_allow_html=True)
    st.markdown("<span id='notice-ok-anchor'></span>", unsafe_allow_html=True)
    st.button("OK", key="notice_ok", on_click=clear_notice)


@st.fragment(run_every=1.0)
def render_fleet_unavailable_overlay():
    if st.session_state.get("fleet_unavailable_until") is None:
        return
    if st.session_state.get("report"):
        state.restart_fleet_unavailable_wait()
        return
    remaining = state.fleet_unavailable_remaining()
    if remaining <= 0:
        state.finish_fleet_unavailable_wait()
        st.rerun()
        return
    st.markdown(f"""
    <div class="fleet-wait-overlay">
      <div class="fleet-wait-card">
        <h3>Все рейсы поставлены на паузу</h3>
        <p>Самолеты авиакомпании недоступны, именно поэтому советую вам копить
        на private jet, мне лично нравится Gulfstream G700. Вот у Дрейка вообще
        Boeing 767, хочу как Дрейк...</p>
        <div class="fleet-wait-timer">{remaining:02d}s</div>
        <div class="fleet-wait-sub">Ожидание обусловлено отсутствием доступных рейсов.</div>
      </div>
    </div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- HUD
def render_hud():
    s = st.session_state
    sel = _display_name(s["selected_aircraft"])
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
        fleet_count = len(data_loader.fleet_ids())
        fleet_word = "борта" if fleet_count == 3 else "бортов"
        k2.markdown(f"<div class='kpi'><div class='k'>Флот PADII</div>"
                    f"<div class='v'>{fleet_count} {fleet_word}</div></div>",
                    unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶  START CAMPAIGN", type="primary", use_container_width=True):
            st.session_state["pending_mode"] = mode
            st.session_state["tutorial_prompt"] = True
            st.rerun()

        if st.session_state.get("tutorial_prompt"):
            pending_mode = st.session_state.get("pending_mode") or mode
            st.markdown("""
            <div class='panel tutorial-card'>
              <h4>Перед стартом</h4>
              <p>Хотите пройти короткое обучение-гайд? Оно покажет, где покупать
              RUL, где читать сенсоры, как работает таймер и какие кнопки отвечают
              за рейс / ТО.</p>
            </div>""", unsafe_allow_html=True)
            t1, t2 = st.columns(2)
            if t1.button("Пройти обучение", type="primary", use_container_width=True):
                st.session_state["screen"] = "tutorial"
                st.session_state["mode"] = pending_mode
                st.session_state["tutorial_prompt"] = False
                st.rerun()
            if t2.button("Пропустить", use_container_width=True):
                start_campaign(pending_mode)
                st.rerun()


def render_tutorial():
    st.markdown("""
    <div class="lobby-hero">
      <div class="t">TRAINING GUIDE</div>
      <div class="s">Короткий briefing перед первой сменой инженера</div>
    </div>
    <div class="panel tutorial-card">
      <h4>Как играть</h4>
      <p><b>1. Outbound Flight</b> — сверху в консоли показан текущий рейс,
      город назначения и таймер 20 секунд.</p>
      <p><b>2. Графики</b> — RUL/ML prediction и сенсоры доступны сразу.
      Истинный RUL раскрывается только после ТО или отказа.</p>
      <p><b>3. Платные подсказки</b> — точное Predicted RUL и System Advice
      покупаются отдельно по $50,000. Если денег не хватает, появится уведомление.</p>
      <p><b>4. Решение</b> — отправьте рейс или снимите двигатель на ТО.
      После таймера ТО блокируется, и рейс уходит поздно.</p>
      <p><b>5. Бюджет</b> — компания не может уйти в минус. Для ТО и аварийных
      штрафов это может завершить кампанию.</p>
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("Понятно, начать кампанию", type="primary", use_container_width=True):
            start_campaign(st.session_state.get("mode", "baseline"))
            st.rerun()


# ---------------------------------------------------------------- FLEET PANEL
def render_fleet_panel(fleet):
    st.markdown("<div class='panel'><h4>Aircraft Fleet</h4>", unsafe_allow_html=True)
    meta = data_loader.load_metadata().set_index("aircraft_id")
    for i, aid in enumerate(fleet):
        s = state.ac_state(aid)
        ep = s["status"]
        if ep == "active":
            revealed = is_revealed(aid, "rul")
            stt = state.status(aid) if revealed else config.STATUS_WARNING
            rul = f"{state.predicted_rul(aid):.0f}" if revealed else "??"
        elif ep == "maintained":
            stt, rul = config.STATUS_WARNING, "TO"
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
            <img class="thumb" src="data:image/png;base64,{_sprite_b64(_fleet_card_sprite(aid))}"/>
            <div class="fleet-info">
              <div class="fleet-top">
                <span class="fleet-id">{_display_name(aid)}</span>
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
        if ep_map[aid] == "maintained":
            status_map[aid] = config.STATUS_WARNING
        elif ep_map[aid] == "crashed":
            status_map[aid] = config.STATUS_CRITICAL
        else:
            status_map[aid] = state.status(aid)
    img, hitboxes = scene.render_airport_cached(
        fleet, st.session_state["selected_aircraft"], status_map, ep_map)

    if st.session_state.get("report"):
        st.image(img, use_container_width=True)
        val = None
    else:
        val = streamlit_image_coordinates(img, key="airport_map", use_column_width=True)
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
def _tick_decision(aid: str | None) -> bool:
    """Per-second timer heartbeat shared by the timer fragments.

    Keeps the pause/resume state in sync and auto-dispatches the outbound
    flight once the 20s window elapses. Returns True when an auto-dispatch
    happened so the caller can trigger a full app rerun.
    """
    if state.notification_active():
        state.pause_timer()
        return False
    if st.session_state.get("timer_paused_at") is not None:
        state.resume_timer()
    if aid and state.decision_time_expired():
        economics.continue_flight(aid)
        return True
    return False


@st.fragment(run_every=1.0)
def _decision_timer_tick(aid: str):
    """Invisible heartbeat used when the active flight is not the selected one,
    so its timer keeps running without rerendering the whole page."""
    if _tick_decision(aid):
        st.rerun()


@st.fragment(run_every=1.0)
def render_live_departure_timer(aid: str):
    if _tick_decision(aid):
        st.rerun()
        return
    remaining = state.remaining_seconds()
    destination = st.session_state.get("destination") or "Unknown"
    paused = st.session_state.get("timer_paused_at") is not None
    cls = "paused" if paused else "danger" if remaining <= 5 else "warn" if remaining <= 10 else "ok"
    timer_text = "PAUSE" if paused else f"{remaining:02d}s"
    st.markdown(f"""
    <div class="departure-card {cls}">
      <div>
        <b>OUTBOUND FLIGHT</b><br>
        PADII dispatch → <span>{destination}</span>
      </div>
      <div class="timer">{timer_text}</div>
    </div>""", unsafe_allow_html=True)
def render_departure_brief(aid: str, is_current: bool):
    if not is_current:
        current = _display_name(st.session_state.get("current_departure"))
        st.markdown(f"""
        <div class="departure-card muted">
          <b>OUTBOUND QUEUE</b><br>
          Сейчас в обработке: <span>{current}</span>. Этот борт можно осмотреть,
          но решение принимается только по текущему рейсу.
        </div>""", unsafe_allow_html=True)
        return

    render_live_departure_timer(aid)


def render_console(aid):
    s = state.ac_state(aid)
    meta = data_loader.load_metadata().set_index("aircraft_id").loc[aid]
    done = s["episode_done"]
    pred = state.predicted_rul(aid)
    stt = state.status(aid)
    health = int(min(100, max(0, pred / 1.4)))
    is_current = aid == st.session_state.get("current_departure")
    rul_revealed = is_revealed(aid, "rul") or done
    advice_revealed = is_revealed(aid, "advice") or done

    head = (f"ENGINE TELEMETRY — {_display_name(aid)} — {meta['engine_model']} "
            f"({meta['engine_id']})")
    st.markdown(f"<div class='panel'><h4>{head}</h4>", unsafe_allow_html=True)
    render_departure_brief(aid, is_current)

    left, mid = st.columns([1.1, 2.4])

    # --- left: metrics + advice
    with left:
        m1, m2 = st.columns(2)
        m1.markdown(f"<div class='metric'><div class='k'>Current Cycle</div>"
                    f"<div class='v'>{s['cycle']}</div></div>", unsafe_allow_html=True)
        rcol = config.COL[{"Safe": "safe", "Warning": "warning",
                           "Critical": "critical"}[stt]]
        if rul_revealed:
            m2.markdown(f"<div class='metric'><div class='k'>Predicted RUL</div>"
                        f"<div class='v big' style='color:{rcol}'>{pred:.0f}</div>"
                        f"<div class='k'>cycles</div></div>", unsafe_allow_html=True)
        else:
            m2.markdown("<div class='metric locked'><div class='k'>Predicted RUL</div>"
                        "<div class='v big'>LOCKED</div>"
                        "<div class='k'>buy for $50k</div></div>", unsafe_allow_html=True)
            if is_current and st.button(f"Купить Predicted RUL −{money(config.HINT_COST)}",
                                        key=f"buy_rul_{aid}", use_container_width=True):
                economics.buy_rul_hint(aid)
                st.rerun()

        if advice_revealed:
            st.markdown(f"<div style='margin:8px 0'><span class='badge {BADGE[stt]}'>"
                        f"{stt.upper()}</span> &nbsp;"
                        f"<span class='fleet-sub'>Health {health}%</span></div>",
                        unsafe_allow_html=True)
            acls, atxt = ADVICE[stt]
            st.markdown(f"<div class='advice {acls}'><b>System Advice</b><br>{atxt}</div>",
                        unsafe_allow_html=True)
        else:
            st.markdown("<div style='margin:8px 0'><span class='badge locked-badge'>"
                        "STATUS LOCKED</span></div>", unsafe_allow_html=True)
            st.markdown("<div class='advice locked-advice'><b>System Advice</b><br>"
                        "Текстовая подсказка скрыта. Решайте по графикам сенсоров "
                        "или купите консультацию ML-инженера.</div>",
                        unsafe_allow_html=True)
            if is_current and st.button(f"Купить текстовую подсказку −{money(config.HINT_COST)}",
                                        key=f"buy_advice_{aid}", use_container_width=True):
                economics.buy_advice_hint(aid)
                st.rerun()

    # --- middle: RUL chart
    with mid:
        fig = _rul_figure(aid, st.session_state["mode"], s["cycle"], done)
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False}, key=f"rul_{aid}")

    # --- bottom: sensor controls + actions (wide, not cramped on the side)
    st.markdown("<div class='console-bottom'>", unsafe_allow_html=True)
    sensors_col, actions_col = st.columns([2.2, 1.2])
    with sensors_col:
        render_sensor_area(aid)
    with actions_col:
        render_action_center(aid, done)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_sensor_area(aid):
    s = state.ac_state(aid)
    catalog = data_loader.load_sensor_catalog()
    keys = list(catalog.keys())

    st.markdown("<div class='sensor-zone' style='font-size:10px;color:var(--dim);"
                "text-transform:uppercase'>Sensors</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    for i, key in enumerate(keys):
        with cols[i % 2]:
            selected = " ✓" if key == st.session_state.get("selected_sensor") else ""
            if st.button(f"{SENSOR_ICONS.get(key,'•')}\n{catalog[key]['label']}{selected}",
                         key=f"sensor_{key}", use_container_width=True):
                st.session_state["selected_sensor"] = key
                st.session_state["sensor_mode"] = "detail"
                st.rerun()

    key = st.session_state.get("selected_sensor") or keys[0]
    fig = _sensor_figure(aid, key, s["cycle"])
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False}, key=f"sens_{aid}_{key}")


def render_action_center(aid, done):
    st.markdown("<div style='font-size:10px;color:var(--dim);text-transform:uppercase'>"
                "Action Center</div>", unsafe_allow_html=True)
    if st.session_state.get("game_over"):
        st.error("Кампания завершена: бюджет не может уйти в минус.")
        st.markdown("<span id='summary-anchor'></span>", unsafe_allow_html=True)
        if st.button("📊 Итоги кампании", use_container_width=True, key="summary_game_over"):
            st.session_state["screen"] = "summary"
            st.rerun()
        return
    ac = state.ac_state(aid)
    if ac["status"] == "maintained":
        turns = int(ac.get("service_turns_remaining", 0))
        st.info(
            f"Борт на техническом обслуживании. Осталось кругов: {turns}. "
            "Выберите другой самолёт или дождитесь возвращения в строй."
        )
        return

    if done:
        st.info("Эпизод по этому борту завершён. Выберите другой самолёт.")
        st.markdown("<span id='summary-anchor'></span>", unsafe_allow_html=True)
        if st.button("📊 Завершить и посмотреть итоги",
                     use_container_width=True, key="summary_done"):
            st.session_state["screen"] = "summary"
            st.rerun()
        return

    if aid != st.session_state.get("current_departure"):
        st.info("Этот борт не первый в очереди. Дождитесь его outbound slot.")
        return

    expired = state.decision_time_expired()
    if expired:
        st.error("Время решения вышло. ТО уже недоступно: рейс уходит без дополнительной подготовки.")

    st.markdown("<span id='flight-anchor'></span>", unsafe_allow_html=True)
    flight_label = "✈  DISPATCH LATE" if expired else f"✈  CONTINUE FLIGHT  +{money(config.FLIGHT_REVENUE)[1:]}"
    if st.button(flight_label,
                 type="primary", use_container_width=True, key="continue_flight"):
        report = economics.continue_flight(aid)
        if report is None:
            st.rerun()

    st.markdown("<span id='maint-anchor'></span>", unsafe_allow_html=True)
    if st.button(f"🔧  SEND TO MAINTENANCE  −$50,000",
                 use_container_width=True, key="maintenance", disabled=expired):
        economics.send_to_maintenance(aid)

    st.markdown("<div class='fleet-sub' style='margin-top:6px'>Следующий рейс "
                "уменьшит истинный ресурс на 1 цикл.</div>", unsafe_allow_html=True)
    st.markdown("<span id='summary-anchor'></span>", unsafe_allow_html=True)
    if st.button("📊 Завершить и посмотреть итоги",
                 use_container_width=True, key="summary_action"):
        st.session_state["screen"] = "summary"
        st.rerun()


# ---------------------------------------------------------------- REPORT
def render_report():
    rep = st.session_state.get("report")
    if not rep:
        return
    state.pause_timer()
    cls = rep["result"]
    rows = (f"<b>Aircraft:</b> {_display_name(rep['aircraft_id'])} &nbsp;·&nbsp; "
            f"<b>Final cycle:</b> {rep['final_cycle']}<br>"
            f"<b>Predicted RUL (на момент решения):</b> {rep['predicted_rul']}<br>"
            f"<b>True RUL (раскрыт):</b> {rep['true_rul']}<br>"
            f"<b>Финансовый итог:</b> {money(rep['profit'])}")
    if rep["wasted_revenue"]:
        rows += (f"<br><b>Потеряно выручки:</b> ~{money(-rep['wasted_revenue'])[1:]} "
                 f"({rep['true_rul']} рейсов × $5,000)")
    warning_icon = "⚠ " if cls in {"crash", "telemetry_end", "bankrupt"} else ""
    st.markdown(f"""
    <div class="report-overlay">
      <div class="report report-modal {cls}">
        <h3>{warning_icon}{rep['title']}</h3>
        <p style="color:var(--ink);font-size:14px;line-height:1.6">{rep['text']}</p>
        <p style="color:var(--dim);font-size:13px;line-height:1.7">{rows}</p>
        <div class="report-required">
          Уведомление обязательно к прочтению: закройте его, чтобы вернуться к аэропорту.
        </div>
      </div>
    </div>""", unsafe_allow_html=True)
    st.markdown("<span id='report-ok-anchor'></span>", unsafe_allow_html=True)
    st.button("✓ Понятно", type="primary", key="report_ok", on_click=close_report)
    st.markdown("<span id='report-summary-anchor'></span>", unsafe_allow_html=True)
    st.button("📊 Итоги кампании", key="report_summary", on_click=report_to_summary)


# ---------------------------------------------------------------- SUMMARY
def render_summary():
    s = st.session_state
    stats = s["stats"]
    err_count = stats["errors_count"]
    mae = stats["errors_sum"] / err_count if err_count else 0.0
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
    current = st.session_state.get("current_departure")
    # Drive the decision timer from a lightweight heartbeat. When the active
    # flight is the selected one, its visible timer fragment (in the console)
    # owns the tick; otherwise an invisible heartbeat keeps it running.
    if (
        not st.session_state.get("game_over")
        and st.session_state.get("decision_deadline") is not None
        and current
        and current != st.session_state["selected_aircraft"]
    ):
        _decision_timer_tick(current)
    render_hud()
    fleet = list(data_loader.fleet_ids())
    top = st.columns([3, 1])
    with top[0]:
        render_map(fleet)
    with top[1]:
        render_fleet_panel(fleet)

    aid = st.session_state["selected_aircraft"]
    if aid:
        render_console(aid)
    render_report()


def main():
    screen = st.session_state["screen"]
    if screen == "lobby":
        render_lobby()
    elif screen == "tutorial":
        render_tutorial()
    elif screen == "summary":
        render_summary()
    else:
        render_airport_screen()
    render_notice()
    # Only mount the fleet-wait fragment (with its 1s heartbeat) while a wait is
    # actually in progress, so idle screens never tick.
    if st.session_state.get("fleet_unavailable_until") is not None:
        render_fleet_unavailable_overlay()


main()
