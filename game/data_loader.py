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


def predicted_rul(aircraft_id: str, cycle: int, variant: str) -> float | None:
    """Precomputed predicted RUL for a given aircraft / cycle / model variant."""
    preds = load_predictions()
    row = preds[(preds.aircraft_id == aircraft_id)
                & (preds.cycle == cycle)
                & (preds.model_variant == variant)]
    if row.empty:
        return None
    return float(row.iloc[0]["predicted_rul"])


def prediction_series(aircraft_id: str, variant: str, up_to_cycle: int) -> pd.DataFrame:
    preds = load_predictions()
    sub = preds[(preds.aircraft_id == aircraft_id)
                & (preds.model_variant == variant)
                & (preds.cycle <= up_to_cycle)].sort_values("cycle")
    return sub[["cycle", "predicted_rul", "true_rul"]].reset_index(drop=True)


def full_truth_series(aircraft_id: str, variant: str) -> pd.DataFrame:
    preds = load_predictions()
    sub = preds[(preds.aircraft_id == aircraft_id)
                & (preds.model_variant == variant)].sort_values("cycle")
    return sub[["cycle", "predicted_rul", "true_rul"]].reset_index(drop=True)


def sensor_series(aircraft_id: str, sensor_key: str, up_to_cycle: int) -> pd.DataFrame:
    sensors = load_sensors()
    sub = sensors[(sensors.aircraft_id == aircraft_id)
                  & (sensors.sensor_name == sensor_key)
                  & (sensors.cycle <= up_to_cycle)].sort_values("cycle")
    return sub[["cycle", "sensor_value"]].reset_index(drop=True)


def total_life(aircraft_id: str) -> int:
    meta = load_metadata()
    return int(meta[meta.aircraft_id == aircraft_id].iloc[0]["total_life"])
