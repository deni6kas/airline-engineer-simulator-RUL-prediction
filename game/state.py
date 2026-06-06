"""Game state management on top of st.session_state.

Nothing here trains a model. We only step a pointer through precomputed data.
"""
from __future__ import annotations

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
        "aircraft_states": {},
        "stats": {
            "flights": 0,
            "maintenances": 0,
            "crashes": 0,
            "errors": [],            # list of abs(pred-true) at decision time
        },
        "level": 7,
        "xp": 1250,
        "xp_next": 2000,
    }


def init_state() -> None:
    for k, v in _defaults().items():
        if k not in st.session_state:
            st.session_state[k] = v


def start_campaign(mode: str) -> None:
    """(Re)initialise a fresh campaign for the chosen model variant."""
    for k, v in _defaults().items():
        st.session_state[k] = v
    st.session_state["mode"] = mode
    st.session_state["screen"] = "airport"

    meta = data_loader.load_metadata()
    states: dict[str, dict] = {}
    for _, r in meta.iterrows():
        states[r["aircraft_id"]] = {
            "cycle": int(r["start_cycle"]),
            "start_cycle": int(r["start_cycle"]),
            "total_life": int(r["total_life"]),
            "status": "active",      # active | maintained | crashed
            "episode_done": False,
            "result": None,
            "flights": 0,
        }
    st.session_state["aircraft_states"] = states
    st.session_state["selected_aircraft"] = meta.iloc[0]["aircraft_id"]


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
