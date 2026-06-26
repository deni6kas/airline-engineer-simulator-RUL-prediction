"""Game state management on top of st.session_state.

Nothing here trains a model. We only step a pointer through precomputed data.
"""
from __future__ import annotations

import random
import time

import streamlit as st

from . import config, data_loader


def _defaults() -> dict:
    return {
        "screen": "lobby",          # lobby | airport | summary
        "mode": "baseline",          # baseline | safety_aware
        "budget": config.START_BUDGET,
        "selected_aircraft": None,
        "sensor_mode": "grid",      # grid | detail
        "selected_sensor": None,
        "report": None,              # dict report currently shown
        "notice": None,
        "tutorial_prompt": False,
        "pending_mode": None,
        "game_over": False,
        "game_over_reason": None,
        "departure_queue": [],
        "current_departure": None,
        "destination": None,
        "decision_started_at": None,
        "decision_deadline": None,
        "timer_paused_at": None,
        "fleet_unavailable_until": None,
        "revealed_rul": {},
        "revealed_advice": {},
        "aircraft_states": {},
        "stats": {
            "flights": 0,
            "maintenances": 0,
            "crashes": 0,
            # running aggregate of abs(pred-true) at decision time, used for MAE
            "errors_sum": 0.0,
            "errors_count": 0,
        },
        "level": 0,
        "xp": 0,
        "xp_next": 100,
    }


def init_state() -> None:
    for k, v in _defaults().items():
        if k not in st.session_state:
            st.session_state[k] = v
    if (
        st.session_state.get("screen") == "airport"
        and st.session_state.get("aircraft_states")
        and not st.session_state.get("current_departure")
    ):
        fleet = list(st.session_state["aircraft_states"].keys())
        st.session_state["departure_queue"] = fleet
        start_departure(st.session_state.get("selected_aircraft") or fleet[0])


def start_campaign(mode: str) -> None:
    """(Re)initialise a fresh campaign for the chosen model variant."""
    for k, v in _defaults().items():
        st.session_state[k] = v
    st.session_state["mode"] = mode
    st.session_state["screen"] = "airport"

    meta = data_loader.load_metadata()
    states: dict[str, dict] = {}
    rng = random.SystemRandom()
    for _, r in meta.iterrows():
        total_life = int(r["total_life"])
        max_available_cycle = int(r["max_available_cycle"])
        # Randomise only inside the precomputed holdout telemetry window.
        # No model training happens at runtime; we just pick another
        # precomputed cycle from the game holdout engines.
        min_start = max(40, max_available_cycle - 45)
        max_start = max(min_start, max_available_cycle - 8)
        start_cycle = rng.randint(min_start, max_start)
        states[r["aircraft_id"]] = {
            "cycle": start_cycle,
            "start_cycle": start_cycle,
            "initial_true_rul": total_life - start_cycle,
            "total_life": total_life,
            "max_available_cycle": max_available_cycle,
            "status": "active",      # active | maintained | crashed
            "episode_done": False,
            "result": None,
            "flights": 0,
            "service_turns_remaining": 0,
        }
    st.session_state["aircraft_states"] = states
    fleet = meta["aircraft_id"].tolist()
    st.session_state["departure_queue"] = fleet
    st.session_state["selected_aircraft"] = fleet[0]
    start_departure(fleet[0], rng)


def start_departure(aircraft_id: str, rng: random.Random | None = None) -> None:
    rng = rng or random.SystemRandom()
    st.session_state["revealed_rul"].pop(aircraft_id, None)
    st.session_state["revealed_advice"].pop(aircraft_id, None)
    st.session_state["current_departure"] = aircraft_id
    st.session_state["selected_aircraft"] = aircraft_id
    st.session_state["destination"] = config.AIRCRAFT_DESTINATIONS.get(
        aircraft_id, rng.choice(config.DESTINATIONS)
    )
    now = time.time()
    st.session_state["decision_started_at"] = now
    st.session_state["decision_deadline"] = now + config.DECISION_SECONDS
    st.session_state["timer_paused_at"] = None
    st.session_state["sensor_mode"] = "grid"
    st.session_state["selected_sensor"] = None


def advance_departure() -> None:
    queue = st.session_state.get("departure_queue", [])
    current = st.session_state.get("current_departure")
    if current in queue:
        queue = [aid for aid in queue if aid != current]
        cur = ac_state(current)
        if not cur["episode_done"] and cur["status"] == "active":
            queue.append(current)
    _progress_maintenance(exclude={current})
    for aid, ac in st.session_state["aircraft_states"].items():
        if not ac["episode_done"] and ac["status"] == "active" and aid not in queue:
            queue.append(aid)
    next_active = None
    for aid in queue:
        ac = ac_state(aid)
        if not ac["episode_done"] and ac["status"] == "active":
            next_active = aid
            break
    if next_active is None:
        if _maintained_fleet_exists():
            st.session_state["departure_queue"] = queue
            _start_fleet_unavailable_wait()
            return
    if next_active is None:
        st.session_state["current_departure"] = None
        st.session_state["destination"] = None
        st.session_state["decision_deadline"] = None
        return
    st.session_state["departure_queue"] = queue
    start_departure(next_active)


def _reset_aircraft_engine(aircraft_id: str) -> None:
    ac = ac_state(aircraft_id)
    rng = random.SystemRandom()
    min_start = max(40, int(ac["max_available_cycle"]) - 45)
    max_start = max(min_start, int(ac["max_available_cycle"]) - 8)
    start_cycle = rng.randint(min_start, max_start)
    ac.update({
        "cycle": start_cycle,
        "start_cycle": start_cycle,
        "initial_true_rul": int(ac["total_life"]) - start_cycle,
        "status": "active",
        "episode_done": False,
        "result": None,
        "flights": 0,
        "service_turns_remaining": 0,
    })
    st.session_state["revealed_rul"].pop(aircraft_id, None)
    st.session_state["revealed_advice"].pop(aircraft_id, None)


def _progress_maintenance(exclude: set[str | None] | None = None) -> None:
    exclude = exclude or set()
    for aid, ac in st.session_state["aircraft_states"].items():
        if aid in exclude or ac["status"] != "maintained":
            continue
        remaining = max(0, int(ac.get("service_turns_remaining", 0)) - 1)
        ac["service_turns_remaining"] = remaining
        if remaining <= 0:
            _reset_aircraft_engine(aid)


def _maintained_fleet_exists() -> bool:
    return any(ac["status"] == "maintained" for ac in st.session_state["aircraft_states"].values())


def _start_fleet_unavailable_wait() -> None:
    st.session_state["current_departure"] = None
    st.session_state["destination"] = None
    st.session_state["decision_deadline"] = None
    st.session_state["timer_paused_at"] = None
    if st.session_state.get("fleet_unavailable_until") is None:
        st.session_state["fleet_unavailable_until"] = time.time() + config.FLEET_UNAVAILABLE_SECONDS


def fleet_unavailable_remaining() -> int:
    until = st.session_state.get("fleet_unavailable_until")
    if until is None:
        return 0
    return max(0, int(round(until - time.time())))


def finish_fleet_unavailable_wait() -> None:
    for aid, ac in st.session_state["aircraft_states"].items():
        if ac["status"] == "maintained":
            _reset_aircraft_engine(aid)
    queue = [
        aid for aid, ac in st.session_state["aircraft_states"].items()
        if not ac["episode_done"]
    ]
    st.session_state["departure_queue"] = queue
    st.session_state["fleet_unavailable_until"] = None
    if queue:
        start_departure(queue[0])


def restart_fleet_unavailable_wait() -> None:
    if st.session_state.get("fleet_unavailable_until") is not None:
        st.session_state["fleet_unavailable_until"] = time.time() + config.FLEET_UNAVAILABLE_SECONDS


def remaining_seconds() -> int:
    deadline = st.session_state.get("decision_deadline")
    if deadline is None or st.session_state.get("game_over"):
        return 0
    now = st.session_state.get("timer_paused_at") or time.time()
    return max(0, int(round(deadline - now)))


def decision_time_expired() -> bool:
    deadline = st.session_state.get("decision_deadline")
    now = st.session_state.get("timer_paused_at") or time.time()
    return bool(deadline is not None and now > deadline)


def notification_active() -> bool:
    return bool(st.session_state.get("report") or st.session_state.get("notice"))


def pause_timer() -> None:
    if st.session_state.get("decision_deadline") is None:
        return
    if st.session_state.get("timer_paused_at") is None:
        st.session_state["timer_paused_at"] = time.time()


def resume_timer() -> None:
    paused_at = st.session_state.get("timer_paused_at")
    if paused_at is None:
        return
    paused_for = time.time() - paused_at
    if st.session_state.get("decision_deadline") is not None:
        st.session_state["decision_deadline"] += paused_for
    st.session_state["timer_paused_at"] = None


# --- accessors -------------------------------------------------------------
def ac_state(aircraft_id: str) -> dict:
    return st.session_state["aircraft_states"][aircraft_id]


def true_rul(aircraft_id: str) -> int:
    s = ac_state(aircraft_id)
    return max(0, s["total_life"] - s["cycle"])


def predicted_rul(aircraft_id: str) -> float:
    s = ac_state(aircraft_id)
    val = data_loader.predicted_rul(aircraft_id, s["cycle"], st.session_state["mode"])
    return float(val) if val is not None else 0.0


def status(aircraft_id: str) -> str:
    s = ac_state(aircraft_id)
    if s["status"] == "crashed":
        return config.STATUS_CRITICAL
    return config.status_for_rul(predicted_rul(aircraft_id))


def all_episodes_done() -> bool:
    return all(s["episode_done"] for s in st.session_state["aircraft_states"].values())
