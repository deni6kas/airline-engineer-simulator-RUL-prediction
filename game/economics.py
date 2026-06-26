"""Financial logic + decision outcomes. The heart of the ML-value demo."""
from __future__ import annotations

import streamlit as st

from . import config, state


def _game_over(reason: str) -> dict:
    st.session_state["game_over"] = True
    st.session_state["game_over_reason"] = reason
    report = {
        "aircraft_id": st.session_state.get("current_departure") or "PADII",
        "result": "bankrupt",
        "title": "Банкротство",
        "text": reason,
        "predicted_rul": 0,
        "true_rul": 0,
        "profit": 0,
        "wasted_revenue": 0,
        "final_cycle": 0,
        "model_variant": st.session_state["mode"],
    }
    st.session_state["report"] = report
    return report


def _record_error(abs_error: float) -> None:
    """Accumulate |predicted - true| for the campaign MAE (running sum/count)."""
    stats = st.session_state["stats"]
    stats["errors_sum"] += abs_error
    stats["errors_count"] += 1


def _mark_game_over_if_negative() -> None:
    if st.session_state["budget"] < 0:
        st.session_state["game_over"] = True
        st.session_state["game_over_reason"] = "Бюджет ушёл в минус. Кампания завершена."


def spend(amount: int, reason: str, bankrupt_on_fail: bool = True) -> bool:
    if st.session_state["budget"] - amount < 0:
        message = f"Недостаточно средств: нужно {amount:,}$ на {reason}."
        if bankrupt_on_fail:
            _game_over(
                f"Бюджет не покрывает расход {amount:,}$: {reason}. "
                "Компания не может уйти в минус, кампания завершена."
            )
        else:
            st.session_state["notice"] = message
            state.pause_timer()
        return False
    st.session_state["budget"] -= amount
    return True


def buy_rul_hint(aircraft_id: str) -> bool:
    if st.session_state["revealed_rul"].get(aircraft_id):
        return True
    if not spend(config.HINT_COST, "покупку Predicted RUL", bankrupt_on_fail=False):
        return False
    st.session_state["revealed_rul"][aircraft_id] = True
    return True


def buy_advice_hint(aircraft_id: str) -> bool:
    if st.session_state["revealed_advice"].get(aircraft_id):
        return True
    if not spend(config.HINT_COST, "покупку текстовой подсказки", bankrupt_on_fail=False):
        return False
    st.session_state["revealed_advice"][aircraft_id] = True
    return True


def continue_flight(aircraft_id: str) -> dict | None:
    """Run one flight cycle. Returns a crash report dict if the engine fails."""
    s = state.ac_state(aircraft_id)
    if s["episode_done"] or s["status"] != "active" or st.session_state.get("game_over"):
        return None

    pred_at_decision = state.predicted_rul(aircraft_id)
    tr = state.true_rul(aircraft_id)

    # Game aircraft are train_FD001 holdout engines with full run-to-failure
    # telemetry. Continuing past the final known cycle means the engine life is
    # exhausted, so it is treated as an in-flight failure.
    if s["cycle"] >= s.get("max_available_cycle", s["total_life"]):
        st.session_state["budget"] -= config.CRASH_PENALTY
        _mark_game_over_if_negative()
        s["status"] = "crashed"
        s["episode_done"] = True
        report = _build_report(
            aircraft_id, result="telemetry_end",
            predicted_rul=pred_at_decision, true_rul=tr,
            profit=-config.CRASH_PENALTY,
        )
        s["result"] = report
        st.session_state["stats"]["crashes"] += 1
        _record_error(abs(pred_at_decision - tr))
        st.session_state["report"] = report
        state.advance_departure()
        return report

    # engine has no life left -> attempting another flight destroys it
    if tr <= 0:
        st.session_state["budget"] -= config.CRASH_PENALTY
        _mark_game_over_if_negative()
        s["status"] = "crashed"
        s["episode_done"] = True
        report = _build_report(
            aircraft_id, result="crash",
            predicted_rul=pred_at_decision, true_rul=0,
            profit=-config.CRASH_PENALTY,
        )
        s["result"] = report
        st.session_state["stats"]["crashes"] += 1
        _record_error(abs(pred_at_decision - 0))
        st.session_state["report"] = report
        state.advance_departure()
        return report

    # successful flight
    s["cycle"] += 1
    s["flights"] += 1
    st.session_state["budget"] += config.FLIGHT_REVENUE
    st.session_state["stats"]["flights"] += 1
    _award_xp(25)
    state.advance_departure()
    return None


def send_to_maintenance(aircraft_id: str) -> dict:
    s = state.ac_state(aircraft_id)
    if st.session_state.get("game_over"):
        return st.session_state.get("report")
    pred_at_decision = state.predicted_rul(aircraft_id)
    tr = state.true_rul(aircraft_id)

    if not spend(config.MAINTENANCE_COST, "отправку самолёта на ТО", bankrupt_on_fail=False):
        return None
    s["status"] = "maintained"
    s["service_turns_remaining"] = config.MAINTENANCE_TURNS
    st.session_state["stats"]["maintenances"] += 1
    _record_error(abs(pred_at_decision - tr))

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
    state.advance_departure()
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
        "telemetry_end": (
            "Отказ двигателя",
            "Ресурс двигателя исчерпан: вы продолжили эксплуатацию после "
            "последнего доступного цикла run-to-failure траектории holdout-"
            "двигателя. Это означает фактический отказ двигателя и крупный "
            "аварийный риск для бизнеса.",
        ),
        "bankrupt": (
            "Банкротство",
            "Компания не может оплачивать решения при отрицательном бюджете. "
            "Кампания завершена.",
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
