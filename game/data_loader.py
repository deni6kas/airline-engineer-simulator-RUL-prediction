"""Load precomputed game data. All values are READ-ONLY model outputs."""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd
import streamlit as st

from . import config


@st.cache_data(show_spinner=False)
def load_aircrafts() -> pd.DataFrame:
    return pd.read_csv(config.DATA_DIR / "aircrafts.csv")


@st.cache_data(show_spinner=False)
def load_metadata() -> pd.DataFrame:
    return pd.read_csv(config.DATA_DIR / "engine_metadata.csv")


@st.cache_data(show_spinner=False)
def load_sensors() -> pd.DataFrame:
    return pd.read_parquet(config.DATA_DIR / "sensors.parquet")


@st.cache_data(show_spinner=False)
def load_predictions() -> pd.DataFrame:
    return pd.read_parquet(config.DATA_DIR / "precomputed_predictions.parquet")


@st.cache_data(show_spinner=False)
def load_sensor_catalog() -> dict:
    path = config.DATA_DIR / "sensor_catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def fleet_ids() -> tuple[str, ...]:
    return tuple(load_metadata()["aircraft_id"].tolist())


@st.cache_data(show_spinner=False)
def _prediction_index() -> dict:
    """Precompute O(1) lookup structures from the predictions table.

    - ``groups[(aircraft_id, variant)]`` -> cycle-sorted DataFrame
      (columns: cycle, predicted_rul, true_rul) identical to the old filtered
      result, so slicing by cycle reproduces ``prediction_series`` exactly.
    - ``point[(aircraft_id, variant, cycle)]`` -> predicted_rul (float).
    """
    preds = load_predictions()
    groups: dict[tuple[str, str], pd.DataFrame] = {}
    point: dict[tuple[str, str, int], float] = {}
    for (aid, variant), sub in preds.groupby(["aircraft_id", "model_variant"], sort=False):
        sub = sub.sort_values("cycle")[["cycle", "predicted_rul", "true_rul"]].reset_index(drop=True)
        groups[(aid, variant)] = sub
        for cycle, pred in zip(sub["cycle"], sub["predicted_rul"]):
            point.setdefault((aid, variant, int(cycle)), float(pred))
    return {"groups": groups, "point": point}


@st.cache_data(show_spinner=False)
def _sensor_index() -> dict:
    """``[(aircraft_id, sensor_name)] -> cycle-sorted DataFrame`` (cycle, sensor_value)."""
    sensors = load_sensors()
    groups: dict[tuple[str, str], pd.DataFrame] = {}
    for (aid, name), sub in sensors.groupby(["aircraft_id", "sensor_name"], sort=False):
        groups[(aid, name)] = (
            sub.sort_values("cycle")[["cycle", "sensor_value"]].reset_index(drop=True)
        )
    return groups


def predicted_rul(aircraft_id: str, cycle: int, variant: str) -> float | None:
    """Precomputed predicted RUL for a given aircraft / cycle / model variant."""
    return _prediction_index()["point"].get((aircraft_id, variant, int(cycle)))


def prediction_series(aircraft_id: str, variant: str, up_to_cycle: int) -> pd.DataFrame:
    sub = _prediction_index()["groups"].get((aircraft_id, variant))
    if sub is None:
        return pd.DataFrame(columns=["cycle", "predicted_rul", "true_rul"])
    return sub[sub["cycle"] <= up_to_cycle].reset_index(drop=True)


def full_truth_series(aircraft_id: str, variant: str) -> pd.DataFrame:
    sub = _prediction_index()["groups"].get((aircraft_id, variant))
    if sub is None:
        return pd.DataFrame(columns=["cycle", "predicted_rul", "true_rul"])
    return sub.reset_index(drop=True)


def sensor_series(aircraft_id: str, sensor_key: str, up_to_cycle: int) -> pd.DataFrame:
    sub = _sensor_index().get((aircraft_id, sensor_key))
    if sub is None:
        return pd.DataFrame(columns=["cycle", "sensor_value"])
    return sub[sub["cycle"] <= up_to_cycle].reset_index(drop=True)


def total_life(aircraft_id: str) -> int:
    meta = load_metadata()
    return int(meta[meta.aircraft_id == aircraft_id].iloc[0]["total_life"])
