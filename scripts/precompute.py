"""Precompute RUL predictions for the PADII RUL Engineer game.

Pipeline (offline, run once):
  1. Load NASA CMAPSS FD001 train trajectories (run-to-failure).
  2. Engineer features from the 4 game sensors.
  3. Train RandomForest with GroupKFold -> honest out-of-fold predictions.
  4. Build two model variants:
        - baseline      : 0.6 * q35 + 0.4 * mean - 1.0   (week-5 best blend)
        - safety_aware  : conservative low-quantile blend (under-predicts RUL,
                          penalises dangerous overestimation -> fewer crashes)
  5. Select a playable PADII fleet and export tidy data files.

The game NEVER trains anything: it only reads the parquet/csv produced here.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# --- paths -----------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_DIR / "data"
MODELS_OUT = PROJECT_DIR / "models"
RESULTS_OUT = PROJECT_DIR / "precomputed_results"

CMAPSS_DIR = Path(
    r"c:\Users\Lenovo\Desktop\Algorithms contest\NASA project"
    r"\aerospace-rul-prediction\CMAPSSData"
)

RUL_CAP = 140  # piecewise-linear RUL clip, matches the notebooks
N_FOLDS = 5

# --- the 4 sensors used by the game (1-based CMAPSS sensor index) ----------
# sensor_4  (col 9)  : LPT outlet temperature
# sensor_9  (col 14) : physical core speed
# sensor_11 (col 16) : HPC outlet static pressure
# sensor_14 (col 19) : corrected core speed
GAME_SENSORS = {
    "sensor_4": {"key": "egt", "label": "Exhaust Temp (LPT out)", "unit": "deg R"},
    "sensor_9": {"key": "core_speed", "label": "Core Speed (Nc)", "unit": "rpm"},
    "sensor_11": {"key": "hpc_pressure", "label": "Compressor Press (Ps30)", "unit": "psia"},
    "sensor_14": {"key": "corr_core_speed", "label": "Corr. Core Speed (NRc)", "unit": "rpm"},
}
SENSOR_COLS = list(GAME_SENSORS.keys())

COLUMNS = [
    "unit_id", "cycle", "op_setting_1", "op_setting_2", "op_setting_3",
    "sensor_1", "sensor_2", "sensor_3", "sensor_4", "sensor_5",
    "sensor_6", "sensor_7", "sensor_8", "sensor_9", "sensor_10",
    "sensor_11", "sensor_12", "sensor_13", "sensor_14", "sensor_15",
    "sensor_16", "sensor_17", "sensor_18", "sensor_19", "sensor_20", "sensor_21",
]

# PADII fleet flavour --------------------------------------------------------
FLEET_MODELS = [
    ("XJ-100", "PD-100"),
    ("XJ-200", "PD-200"),
    ("XJ-300", "PD-300"),
]
N_AIRCRAFT = len(FLEET_MODELS)


def load_train() -> pd.DataFrame:
    path = CMAPSS_DIR / "train_FD001.txt"
    df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    df = df.iloc[:, : len(COLUMNS)]
    df.columns = COLUMNS
    max_cycle = df.groupby("unit_id")["cycle"].transform("max")
    df["RUL"] = (max_cycle - df["cycle"]).clip(upper=RUL_CAP)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-engine features from the 4 game sensors: value, rolling stats, delta."""
    feats = df[["unit_id", "cycle"]].copy()
    for col in SENSOR_COLS:
        g = df.groupby("unit_id")[col]
        feats[f"{col}_val"] = df[col]
        feats[f"{col}_roll_mean"] = g.transform(lambda s: s.rolling(5, min_periods=1).mean())
        feats[f"{col}_roll_std"] = g.transform(lambda s: s.rolling(5, min_periods=1).std().fillna(0.0))
        # deviation from the engine's own healthy baseline (first 5 cycles)
        base = g.transform(lambda s: s.iloc[:5].mean())
        feats[f"{col}_dev"] = df[col] - base
    return feats


def oof_quantile_predictions(X: np.ndarray, y: np.ndarray, groups: np.ndarray):
    """Out-of-fold RF predictions: returns per-row mean + chosen quantiles."""
    gkf = GroupKFold(n_splits=N_FOLDS)
    n = len(y)
    pred_mean = np.zeros(n)
    pred_q20 = np.zeros(n)
    pred_q35 = np.zeros(n)
    for tr, va in gkf.split(X, y, groups):
        rf = RandomForestRegressor(
            n_estimators=300, max_features=0.6, min_samples_leaf=5,
            random_state=RANDOM_STATE, n_jobs=-1,
        )
        rf.fit(X[tr], y[tr])
        # stack predictions from every tree -> distribution per sample
        tree_preds = np.stack([t.predict(X[va]) for t in rf.estimators_], axis=1)
        pred_mean[va] = tree_preds.mean(axis=1)
        pred_q20[va] = np.quantile(tree_preds, 0.20, axis=1)
        pred_q35[va] = np.quantile(tree_preds, 0.35, axis=1)
    return pred_mean, pred_q20, pred_q35


def main() -> None:
    for d in (DATA_OUT, MODELS_OUT, RESULTS_OUT):
        d.mkdir(parents=True, exist_ok=True)

    print("Loading CMAPSS FD001 train ...")
    df = load_train()
    feats = build_features(df)
    feature_cols = [c for c in feats.columns if c not in ("unit_id", "cycle")]

    X = feats[feature_cols].to_numpy()
    y = df["RUL"].to_numpy()
    groups = df["unit_id"].to_numpy()

    print("Training RandomForest (GroupKFold OOF) ...")
    pred_mean, pred_q20, pred_q35 = oof_quantile_predictions(X, y, groups)

    # --- two model variants -------------------------------------------------
    baseline = 0.6 * pred_q35 + 0.4 * pred_mean - 1.0
    safety = 0.70 * pred_q20 + 0.30 * pred_q35 - 2.0  # more conservative
    baseline = np.clip(baseline, 0, RUL_CAP)
    safety = np.clip(safety, 0, RUL_CAP)

    work = df[["unit_id", "cycle", "RUL"] + SENSOR_COLS].copy()
    work["pred_baseline"] = baseline
    work["pred_safety_aware"] = safety
    work["true_rul"] = (work.groupby("unit_id")["cycle"].transform("max") - work["cycle"])

    # --- pick a diverse playable fleet -------------------------------------
    life = df.groupby("unit_id")["cycle"].max().sort_values()
    # spread choices across short / medium / long lived engines
    idx = np.linspace(0, len(life) - 1, N_AIRCRAFT).round().astype(int)
    chosen_units = life.index[idx].tolist()
    print(f"Selected engines (unit_id): {chosen_units}")

    aircrafts_rows = []
    meta_rows = []
    sensors_long = []
    preds_long = []

    for i, unit in enumerate(chosen_units):
        sub = work[work["unit_id"] == unit].sort_values("cycle").reset_index(drop=True)
        total_life = int(sub["cycle"].max())
        model_name, engine_model = FLEET_MODELS[i]
        aircraft_id = f"PADII-{101 + i * 101 if i < 1 else 101 + i}"  # readable-ish
        aircraft_id = f"PADII-{(i + 1) * 101 if (i + 1) * 101 < 1000 else 100 + i}"
        aircraft_id = f"PADII-{[101, 202, 303, 404, 505, 606][i]}"
        engine_id = f"ENG-{37 + i * 11:03d}"

        # start so that true RUL leaves a meaningful but tense runway
        target_start_true = [32, 28, 26, 34, 24, 38][i]
        start_cycle = max(8, total_life - target_start_true)
        start_cycle = min(start_cycle, total_life - 5)
        start_row = sub[sub["cycle"] == start_cycle].iloc[0]

        meta_rows.append({
            "aircraft_id": aircraft_id,
            "engine_id": engine_id,
            "model_name": model_name,
            "engine_model": engine_model,
            "cmapss_unit": int(unit),
            "total_life": total_life,
            "start_cycle": int(start_cycle),
        })

        aircrafts_rows.append({
            "aircraft_id": aircraft_id,
            "engine_id": engine_id,
            "model_name": model_name,
            "engine_model": engine_model,
            "current_cycle": int(start_cycle),
            "true_rul": int(start_row["true_rul"]),
            "predicted_rul": float(start_row["pred_baseline"]),
            "status": "active",
            "is_active": True,
        })

        for _, r in sub.iterrows():
            cyc = int(r["cycle"])
            for variant, col in (("baseline", "pred_baseline"),
                                  ("safety_aware", "pred_safety_aware")):
                preds_long.append({
                    "aircraft_id": aircraft_id,
                    "cycle": cyc,
                    "predicted_rul": float(r[col]),
                    "model_variant": variant,
                    "true_rul": int(r["true_rul"]),
                })
            for scol in SENSOR_COLS:
                sensors_long.append({
                    "aircraft_id": aircraft_id,
                    "cycle": cyc,
                    "sensor_name": GAME_SENSORS[scol]["key"],
                    "sensor_label": GAME_SENSORS[scol]["label"],
                    "sensor_value": float(r[scol]),
                })

    aircrafts = pd.DataFrame(aircrafts_rows)
    meta = pd.DataFrame(meta_rows)
    sensors = pd.DataFrame(sensors_long)
    preds = pd.DataFrame(preds_long)

    aircrafts.to_csv(DATA_OUT / "aircrafts.csv", index=False)
    meta.to_csv(DATA_OUT / "engine_metadata.csv", index=False)
    sensors.to_parquet(DATA_OUT / "sensors.parquet", index=False)
    preds.to_parquet(DATA_OUT / "precomputed_predictions.parquet", index=False)

    sensor_catalog = {v["key"]: {"label": v["label"], "unit": v["unit"]}
                      for v in GAME_SENSORS.values()}
    (DATA_OUT / "sensor_catalog.json").write_text(
        json.dumps(sensor_catalog, indent=2), encoding="utf-8")

    print("\nWrote:")
    for f in ("aircrafts.csv", "engine_metadata.csv", "sensors.parquet",
              "precomputed_predictions.parquet", "sensor_catalog.json"):
        print("  data/" + f)
    print(f"\nFleet: {len(aircrafts)} aircraft, "
          f"{preds['cycle'].nunique()} unique cycles, "
          f"{len(sensors)} sensor points.")


if __name__ == "__main__":
    main()
