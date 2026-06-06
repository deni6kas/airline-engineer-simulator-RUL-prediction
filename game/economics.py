"""Financial logic + decision outcomes. The heart of the ML-value demo."""
from __future__ import annotations

import streamlit as st

from . import config, state


def continue_flight(aircraft_id: str) -> dict | None:
    """Run one flight cycle. Returns a crash report dict if the engine fails."""
    s = state.ac_state(aircraft_id)
    if s["episode_done"]:
        return None

    pred_at_decision = state.predicted_rul(aircraft_id)
    tr = state.true_rul(aircraft_id)

    # engine has no life left -> attempting another flight destroys it
    if tr <= 0:
        st.session_state["budget"] -= config.CRASH_PENALTY
        s["status"] = "crashed"
        s["episode_done"] = True
        report = _build_report(
            aircraft_id, result="crash",
            predicted_rul=pred_at_decision, true_rul=0,
            profit=-config.CRASH_PENALTY,
        )
        s["result"] = report
        st.session_state["stats"]["crashes"] += 1
        st.session_state["stats"]["errors"].append(abs(pred_at_decision - 0))
        st.session_state["report"] = report
        return report

    # successful flight
    s["cycle"] += 1
    s["flights"] += 1
    st.session_state["budget"] += config.FLIGHT_REVENUE
    st.session_state["stats"]["flights"] += 1
    _award_xp(25)
    return None


def send_to_maintenance(aircraft_id: str) -> dict:
    s = state.ac_state(aircraft_id)
    pred_at_decision = state.predicted_rul(aircraft_id)
    tr = state.true_rul(aircraft_id)

    st.session_state["budget"] -= config.MAINTENANCE_COST
    s["status"] = "maintained"
    s["episode_done"] = True
    st.session_state["stats"]["maintenances"] += 1
    st.session_state["stats"]["errors"].append(abs(pred_at_decision - tr))

    # classify outcome by the *true* remaining life at decision time
    if tr <= 12:
        result = "ideal"
        profit = -config.MAINTENANCE_COST
    elif tr <= 25:
        result = "good"
        profit = -config.MAINTENANCE_COST
    else:
        result = "early"
        profit = -config.MAINTENANCE_COST

    report = _build_report(
        aircraft_id, result=result,
        predicted_rul=pred_at_decision, true_rul=tr, profit=profit,
    )
    s["result"] = report
    st.session_state["report"] = report
    _award_xp(40)
    return report


def _build_report(aircraft_id, result, predicted_rul, true_rul, profit) -> dict:
    wasted = max(0, true_rul) * config.FLIGHT_REVENUE
    messages = {
        "ideal": (
            "Идеальное обслуживание",
            "Вы выжали из двигателя максимум ресурса и безопасно заменили его "
            "перед отказом. Прогноз RUL сработал как опора для решения.",
        ),
        "good": (
            "Обоснованное обслуживание",
            "Двигатель снят с небольшим запасом ресурса. Разумный баланс между "
            "безопасностью и прибылью.",
        ),
        "early": (
            "Слишком ранняя замена",
            "Двигатель снят с крыла раньше времени. Потеряна потенциальная "
            "выручка — модель (или решение) оказались излишне осторожны.",
        ),
        "crash": (
            "Авария в воздухе",
            "Двигатель разрушился в полёте. Модель не предупредила вовремя — "
            "именно это и есть цена ошибки прогноза RUL.",
        ),
    }
    title, text = messages[result]
    return {
        "aircraft_id": aircraft_id,
        "result": result,
        "title": title,
        "text": text,
        "predicted_rul": round(float(predicted_rul), 1),
        "true_rul": int(true_rul),
        "profit": int(profit),
        "wasted_revenue": int(wasted) if result == "early" else 0,
        "final_cycle": state.ac_state(aircraft_id)["cycle"],
        "model_variant": st.session_state["mode"],
    }


def _award_xp(amount: int) -> None:
    st.session_state["xp"] += amount
    while st.session_state["xp"] >= st.session_state["xp_next"]:
        st.session_state["xp"] -= st.session_state["xp_next"]
        st.session_state["level"] += 1
        st.session_state["xp_next"] = int(st.session_state["xp_next"] * 1.25)
