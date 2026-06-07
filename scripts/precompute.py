"""Precompute RUL predictions for PADII RUL Engineer.

This script mirrors the Lev Week 6 notebooks:

* `lev_week6_oof_multiview_stacking.ipynb`
  - aggregated history features over operation settings + all 21 sensors
  - RandomForest candidate from week 4
  - tree-distribution q35/mean baseline
  - OOF residual correction with RF_depth6, clip=5, shift=2.0

* `lev_week6_safety_aware_extension.ipynb`
  - safety-aware variant is the conservative, overestimation-averse version
    of the same tree distribution (lower quantile + shift).

Important game constraint:
Official `test_FD001` is truncated, so it does not contain future sensor rows
until failure. For an interactive game we need true failure-cycle and sensors at
every step. Therefore, game aircraft are **holdout engines from train_FD001**:
they are excluded from model training, but retain full run-to-failure telemetry.

The game itself NEVER trains a model. It only reads files produced here.
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

LEV_CAP = 140
LEV_Q = 0.35
LEV_Q_WEIGHT = 0.6
LEV_MEAN_WEIGHT = 0.4
LEV_SHIFT = 1.0
LEV_FINAL_CORRECTION_MODEL_NAME = "RF_depth6"
LEV_FINAL_CORRECTION_CLIP = 5
LEV_FINAL_CORRECTION_SHIFT = 2.0
META_CORRECTION_CLIPS = [3, 5, 7, 10]
validation_target_ruls = [10, 20, 30, 50, 70, 90, 110, 130]
eps = 1e-6

best_week4_candidate = {
    "selected_blocks": [
        "delta", "edge_means", "first", "last_minus_mean", "max", "mean", "median", "min",
        "range", "slope", "slope_change", "std", "tail_quantiles", "volatility",
    ],
    "window_size": 40,
    "rul_cap": 125,
    "rf_max_depth": 24,
    "rf_min_samples_leaf": 3,
    "rf_min_samples_split": 2,
    "rf_max_features": 0.4,
}
final_rf_base = {"n_estimators": 400, "random_state": RANDOM_STATE, "n_jobs": -1}

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
ALL_SENSOR_COLS = [f"sensor_{i}" for i in range(1, 22)]
OP_SETTING_COLS = ["op_setting_1", "op_setting_2", "op_setting_3"]
feature_source_cols = OP_SETTING_COLS + ALL_SENSOR_COLS

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
    df["true_rul"] = max_cycle - df["cycle"]
    return df


def calculate_slope(values):
    values = np.asarray(values, dtype=float)
    if len(values) <= 1:
        return 0.0
    x = np.arange(len(values), dtype=float)
    x = x - x.mean()
    denominator = np.sum(x ** 2)
    if denominator == 0:
        return 0.0
    return float(np.dot(values, x) / denominator)


def calculate_rms(values):
    values = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(values ** 2))) if len(values) else 0.0


def calculate_slope_change(values):
    values = np.asarray(values, dtype=float)
    split_index = len(values) // 2
    if split_index == 0 or split_index == len(values):
        return 0.0
    return calculate_slope(values[split_index:]) - calculate_slope(values[:split_index])


def calculate_volatility(values):
    values = np.asarray(values, dtype=float)
    if len(values) <= 1:
        return 0.0
    return float(np.mean(np.abs(np.diff(values))))


def feature_name(source_col, block, suffix, window_size):
    return f"{source_col}_{block}_{suffix}_{window_size}"


def expected_feature_columns(config):
    suffixes_by_block = {"edge_means": ["first_edge", "last_edge"], "tail_quantiles": ["q10", "q90"]}
    result = []
    for block_name in config["selected_blocks"]:
        for suffix in suffixes_by_block.get(block_name, ["value"]):
            for source_col in feature_source_cols:
                result.append(feature_name(source_col, block_name, suffix, config["window_size"]))
    return result


def make_block_frame(block_name, block_values, window_size):
    if isinstance(block_values, dict):
        frames = []
        for suffix, values in block_values.items():
            frame = values.copy()
            frame.columns = [feature_name(col, block_name, suffix, window_size) for col in frame.columns]
            frames.append(frame)
        return pd.concat(frames, axis=1)
    frame = block_values.copy()
    frame.columns = [feature_name(col, block_name, "value", window_size) for col in frame.columns]
    return frame


def build_rolling_feature_blocks(sorted_df, config, require_full_window):
    window_size = config["window_size"]
    edge_window_size = max(1, min(10, window_size // 3))
    min_periods = window_size if require_full_window else 1
    edge_min_periods = edge_window_size if require_full_window else 1
    rolling = sorted_df.groupby("unit_id")[feature_source_cols].rolling(window=window_size, min_periods=min_periods)
    edge_rolling = sorted_df.groupby("unit_id")[feature_source_cols].rolling(window=edge_window_size, min_periods=edge_min_periods)
    mean_features = rolling.mean().reset_index(level=0, drop=True)
    std_features = rolling.std(ddof=0).reset_index(level=0, drop=True).fillna(0)
    min_features = rolling.min().reset_index(level=0, drop=True)
    max_features = rolling.max().reset_index(level=0, drop=True)
    median_features = rolling.median().reset_index(level=0, drop=True)
    q10_features = rolling.quantile(0.10).reset_index(level=0, drop=True)
    q25_features = rolling.quantile(0.25).reset_index(level=0, drop=True)
    q75_features = rolling.quantile(0.75).reset_index(level=0, drop=True)
    q90_features = rolling.quantile(0.90).reset_index(level=0, drop=True)
    first_features = sorted_df.groupby("unit_id")[feature_source_cols].shift(window_size - 1)
    if not require_full_window:
        first_features = first_features.fillna(sorted_df.groupby("unit_id")[feature_source_cols].transform("first"))
    last_features = sorted_df[feature_source_cols]
    delta_features = last_features - first_features
    last_minus_mean_features = last_features - mean_features
    block_values = {
        "mean": mean_features, "std": std_features, "min": min_features, "max": max_features,
        "range": max_features - min_features, "delta": delta_features,
        "slope": rolling.apply(calculate_slope, raw=True).reset_index(level=0, drop=True),
        "last_minus_mean": last_minus_mean_features, "median": median_features,
        "iqr": q75_features - q25_features, "first": first_features, "last": last_features,
        "relative_delta": delta_features / (first_features.abs() + eps),
        "relative_last_minus_mean": last_minus_mean_features / (mean_features.abs() + eps),
        "rms": rolling.apply(calculate_rms, raw=True).reset_index(level=0, drop=True),
        "edge_means": {
            "first_edge": rolling.apply(lambda values: np.mean(values[:edge_window_size]), raw=True).reset_index(level=0, drop=True),
            "last_edge": edge_rolling.mean().reset_index(level=0, drop=True),
        },
        "slope_change": rolling.apply(calculate_slope_change, raw=True).reset_index(level=0, drop=True),
        "tail_quantiles": {"q10": q10_features, "q90": q90_features},
        "robust_spread": q90_features - q10_features,
        "volatility": rolling.apply(calculate_volatility, raw=True).reset_index(level=0, drop=True),
    }
    return pd.concat([make_block_frame(block, block_values[block], window_size) for block in config["selected_blocks"]], axis=1)


def single_history_feature_row(history_df, config):
    window_size = config["window_size"]
    edge_window_size = max(1, min(10, window_size // 3))
    window_df = history_df.sort_values("cycle").tail(window_size)
    if len(window_df) == 0:
        raise ValueError("empty history cutoff")
    row = {}
    for col in feature_source_cols:
        values = window_df[col].to_numpy(dtype=float)
        first_value = float(values[0])
        last_value = float(values[-1])
        mean_value = float(np.mean(values))
        min_value = float(np.min(values))
        max_value = float(np.max(values))
        q10_value = float(np.quantile(values, 0.10))
        q25_value = float(np.quantile(values, 0.25))
        q75_value = float(np.quantile(values, 0.75))
        q90_value = float(np.quantile(values, 0.90))
        values_by_block = {
            "mean": [("value", mean_value)], "std": [("value", float(np.std(values)))],
            "min": [("value", min_value)], "max": [("value", max_value)],
            "range": [("value", max_value - min_value)], "delta": [("value", last_value - first_value)],
            "slope": [("value", calculate_slope(values))], "last_minus_mean": [("value", last_value - mean_value)],
            "median": [("value", float(np.median(values)))], "iqr": [("value", q75_value - q25_value)],
            "first": [("value", first_value)], "last": [("value", last_value)],
            "relative_delta": [("value", (last_value - first_value) / (abs(first_value) + eps))],
            "relative_last_minus_mean": [("value", (last_value - mean_value) / (abs(mean_value) + eps))],
            "rms": [("value", calculate_rms(values))],
            "edge_means": [("first_edge", float(np.mean(values[:edge_window_size]))), ("last_edge", float(np.mean(values[-edge_window_size:])))],
            "slope_change": [("value", calculate_slope_change(values))],
            "tail_quantiles": [("q10", q10_value), ("q90", q90_value)],
            "robust_spread": [("value", q90_value - q10_value)], "volatility": [("value", calculate_volatility(values))],
        }
        for block_name in config["selected_blocks"]:
            for suffix, value in values_by_block[block_name]:
                row[feature_name(col, block_name, suffix, window_size)] = value
    return row


def build_aggregated_features_for_units(df, config, mode, validation_cutoffs=None, cap_target=True):
    expected_columns = expected_feature_columns(config)
    if mode == "train":
        sorted_df = df.sort_values(["unit_id", "cycle"]).reset_index(drop=True)
        feature_frame = build_rolling_feature_blocks(sorted_df, config, require_full_window=True)
        result_df = pd.concat([sorted_df[["unit_id", "cycle", "RUL"]], feature_frame], axis=1)
        result_df = result_df[result_df["cycle"] >= config["window_size"]].dropna().reset_index(drop=True)
        X = result_df[expected_columns]
        y = result_df["RUL"].reset_index(drop=True)
        if cap_target and config["rul_cap"] is not None:
            y = y.clip(upper=config["rul_cap"])
        return X, y
    if mode == "validation_cutoff":
        grouped = {unit_id: unit_df.sort_values("cycle") for unit_id, unit_df in df.groupby("unit_id")}
        rows, y_values, ids = [], [], []
        for validation_row in validation_cutoffs.itertuples(index=False):
            history_df = grouped[validation_row.unit_id]
            history_df = history_df[history_df["cycle"] <= validation_row.cutoff_cycle]
            rows.append(single_history_feature_row(history_df, config))
            y_values.append(validation_row.true_rul)
            ids.append(f"{validation_row.unit_id}_{validation_row.cutoff_cycle}")
        X = pd.DataFrame(rows).reindex(columns=expected_columns)
        if X.isna().any().any():
            raise ValueError("cutoff features contain NaN")
        return X, pd.Series(y_values), pd.Series(ids)
    raise ValueError(f"Unknown mode: {mode}")


def build_rf_params(candidate, base):
    params = base.copy()
    params.update({
        "max_depth": candidate["rf_max_depth"],
        "min_samples_leaf": candidate["rf_min_samples_leaf"],
        "min_samples_split": candidate["rf_min_samples_split"],
        "max_features": candidate["rf_max_features"],
    })
    return params


def lev_tree_summary(tree_predictions):
    lev_mean_prediction = tree_predictions.mean(axis=0)
    lev_q20 = np.quantile(tree_predictions, 0.20, axis=0)
    lev_q35 = np.quantile(tree_predictions, LEV_Q, axis=0)
    lev_q50 = np.quantile(tree_predictions, 0.50, axis=0)
    lev_q80 = np.quantile(tree_predictions, 0.80, axis=0)
    lev_tree_std = tree_predictions.std(axis=0)
    lev_tree_iqr = lev_q80 - lev_q20
    lev_base_before_residual = np.maximum(LEV_Q_WEIGHT * lev_q35 + LEV_MEAN_WEIGHT * lev_mean_prediction - LEV_SHIFT, 0)
    return pd.DataFrame({
        "lev_mean_prediction": lev_mean_prediction,
        "lev_q20": lev_q20,
        "lev_q35": lev_q35,
        "lev_q50": lev_q50,
        "lev_q80": lev_q80,
        "lev_tree_std": lev_tree_std,
        "lev_tree_iqr": lev_tree_iqr,
        "lev_base_before_residual": lev_base_before_residual,
    })


def lev_calibration_features(summary_df):
    result = summary_df[["lev_base_before_residual", "lev_mean_prediction", "lev_q20", "lev_q35", "lev_q50", "lev_q80", "lev_tree_std", "lev_tree_iqr"]].copy()
    result["lev_mean_minus_q35"] = result["lev_mean_prediction"] - result["lev_q35"]
    result["lev_q80_minus_q35"] = result["lev_q80"] - result["lev_q35"]
    result["lev_q35_minus_q20"] = result["lev_q35"] - result["lev_q20"]
    result["lev_predicted_near_flag"] = (result["lev_base_before_residual"] <= 30).astype(int)
    result["lev_predicted_warning_flag"] = ((result["lev_base_before_residual"] > 30) & (result["lev_base_before_residual"] <= 70)).astype(int)
    result["lev_predicted_long_flag"] = (result["lev_base_before_residual"] > 120).astype(int)
    return result


def make_target_rul_cutoffs(valid_df, target_ruls, window_size):
    rows = []
    for unit_id, unit_df in valid_df.groupby("unit_id"):
        max_cycle = int(unit_df["cycle"].max())
        for target_rul in target_ruls:
            cutoff_cycle = max_cycle - int(target_rul)
            if cutoff_cycle > 0 and cutoff_cycle >= window_size:
                rows.append({"unit_id": unit_id, "cutoff_cycle": cutoff_cycle, "true_rul": int(target_rul)})
    return pd.DataFrame(rows).drop_duplicates(["unit_id", "cutoff_cycle"]).reset_index(drop=True)


def make_all_cycle_cutoffs(game_df, window_size):
    rows = []
    for unit_id, unit_df in game_df.groupby("unit_id"):
        max_cycle = int(unit_df["cycle"].max())
        for cycle in range(window_size, max_cycle + 1):
            rows.append({"unit_id": unit_id, "cutoff_cycle": cycle, "true_rul": max_cycle - cycle})
    return pd.DataFrame(rows)


def train_lev_model(train_part_df):
    candidate = best_week4_candidate.copy()
    candidate["rul_cap"] = LEV_CAP
    X_train, y_train_raw = build_aggregated_features_for_units(train_part_df, candidate, "train", cap_target=False)
    y_train = y_train_raw.clip(upper=LEV_CAP)
    model = RandomForestRegressor(**build_rf_params(candidate, final_rf_base))
    model.fit(X_train, y_train)
    return model, candidate, X_train.shape[1]


def predict_lev_cutoffs(model, candidate, valid_part_df, cutoffs_df):
    X_valid, y_valid, valid_ids = build_aggregated_features_for_units(valid_part_df, candidate, "validation_cutoff", validation_cutoffs=cutoffs_df, cap_target=False)
    X_values = X_valid.to_numpy()
    tree_predictions = np.array([tree.predict(X_values) for tree in model.estimators_])
    summary = lev_tree_summary(tree_predictions)
    return summary, y_valid.reset_index(drop=True), valid_ids.reset_index(drop=True), X_valid.shape[1]


def lev_correction_model_factories():
    return {
        "RF_depth4": lambda: RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=5, min_samples_split=10, max_features="sqrt", random_state=RANDOM_STATE, n_jobs=-1),
        "RF_depth6": lambda: RandomForestRegressor(n_estimators=300, max_depth=6, min_samples_leaf=4, min_samples_split=8, max_features="sqrt", random_state=RANDOM_STATE, n_jobs=-1),
    }


def build_oof_residual_training_df(model_train_df):
    unit_ids = np.array(sorted(model_train_df["unit_id"].unique()))
    group_kfold = GroupKFold(n_splits=N_FOLDS)
    rows = []
    for _, (train_idx, valid_idx) in enumerate(group_kfold.split(unit_ids, groups=unit_ids), start=1):
        fold_train_units = set(unit_ids[train_idx])
        fold_valid_units = set(unit_ids[valid_idx])
        fold_train_df = model_train_df[model_train_df["unit_id"].isin(fold_train_units)].copy()
        fold_valid_df = model_train_df[model_train_df["unit_id"].isin(fold_valid_units)].copy()
        cutoffs_df = make_target_rul_cutoffs(fold_valid_df, validation_target_ruls, best_week4_candidate["window_size"])
        if len(cutoffs_df) == 0:
            continue
        lev_model, lev_candidate, _ = train_lev_model(fold_train_df)
        summary, y_valid, valid_ids, _ = predict_lev_cutoffs(lev_model, lev_candidate, fold_valid_df, cutoffs_df)
        fold_df = summary.copy()
        fold_df["target_rul"] = y_valid.to_numpy()
        fold_df["unit_id"] = [int(str(v).split("_")[0]) for v in valid_ids]
        fold_df["pred_lev_base"] = fold_df["lev_base_before_residual"]
        rows.append(fold_df)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    for d in (DATA_OUT, MODELS_OUT, RESULTS_OUT):
        d.mkdir(parents=True, exist_ok=True)

    print("Loading CMAPSS FD001 train run-to-failure trajectories ...")
    full_train_df = load_train()

    # Game aircraft are held out from training, but keep full lifecycle.
    # These units are deliberately varied in lifetime, so gameplay differs.
    life = full_train_df.groupby("unit_id")["cycle"].max().sort_values()
    idx = np.linspace(0, len(life) - 1, N_AIRCRAFT + 2).round().astype(int)[1:-1]
    chosen_units = life.index[idx].astype(int).tolist()
    game_df = full_train_df[full_train_df["unit_id"].isin(chosen_units)].copy()
    model_train_df = full_train_df[~full_train_df["unit_id"].isin(chosen_units)].copy()
    print(f"Game holdout engines (not used for model training): {chosen_units}")

    print("Training Lev Week6 OOF residual correction on model-train units ...")
    oof_df = build_oof_residual_training_df(model_train_df)
    oof_features = lev_calibration_features(
        oof_df[[
            "lev_base_before_residual", "lev_mean_prediction", "lev_q20",
            "lev_q35", "lev_q50", "lev_q80", "lev_tree_std", "lev_tree_iqr",
        ]]
    )
    residual_target = oof_df["target_rul"].to_numpy() - oof_df["pred_lev_base"].to_numpy()
    lev_correction_model = lev_correction_model_factories()[LEV_FINAL_CORRECTION_MODEL_NAME]()
    lev_correction_model.fit(oof_features, residual_target)

    print("Training final Lev aggregated RF (model-train units only) ...")
    lev_model, lev_candidate, lev_feature_count = train_lev_model(model_train_df)

    print("Predicting every game cycle with Lev OOF model variants ...")
    cutoffs_df = make_all_cycle_cutoffs(game_df, lev_candidate["window_size"])
    lev_summary, y_game, valid_ids, _ = predict_lev_cutoffs(
        lev_model, lev_candidate, game_df, cutoffs_df
    )
    lev_features = lev_calibration_features(lev_summary)
    predicted_residual = lev_correction_model.predict(lev_features)
    pred_oof = np.maximum(
        lev_summary["lev_base_before_residual"].to_numpy()
        + np.clip(predicted_residual, -LEV_FINAL_CORRECTION_CLIP, LEV_FINAL_CORRECTION_CLIP)
        - LEV_FINAL_CORRECTION_SHIFT,
        0,
    )

    # Safety-aware extension: more conservative lower-quantile variant using
    # the same tree distribution from the safety-aware notebook idea.
    pred_safety = np.maximum(
        0.70 * lev_summary["lev_q20"].to_numpy()
        + 0.30 * lev_summary["lev_q35"].to_numpy()
        - 2.0,
        0,
    )

    pred_table = pd.DataFrame({
        "unit_id": [int(str(v).split("_")[0]) for v in valid_ids],
        "cycle": [int(str(v).split("_")[1]) for v in valid_ids],
        "true_rul": y_game.astype(int).to_numpy(),
        "pred_oof": pred_oof,
        "pred_safety_aware": pred_safety,
    })

    work = game_df[["unit_id", "cycle", "true_rul"] + SENSOR_COLS].merge(
        pred_table, on=["unit_id", "cycle", "true_rul"], how="inner"
    )

    aircrafts_rows = []
    meta_rows = []
    sensors_long = []
    preds_long = []

    for i, unit in enumerate(chosen_units):
        sub = work[work["unit_id"] == unit].sort_values("cycle").reset_index(drop=True)
        max_available_cycle = int(sub["cycle"].max())
        total_life = int(max_available_cycle)
        model_name, engine_model = FLEET_MODELS[i]
        aircraft_id = f"PADII-{101 + i * 101 if i < 1 else 101 + i}"  # readable-ish
        aircraft_id = f"PADII-{(i + 1) * 101 if (i + 1) * 101 < 1000 else 100 + i}"
        aircraft_id = f"PADII-{[101, 202, 303, 404, 505, 606][i]}"
        engine_id = f"ENG-{37 + i * 11:03d}"

        # fallback start; actual campaign start is randomized in game/state.py
        start_cycle = max(1, max_available_cycle - 20)
        start_row = sub[sub["cycle"] == start_cycle].iloc[0]

        meta_rows.append({
            "aircraft_id": aircraft_id,
            "engine_id": engine_id,
            "model_name": model_name,
            "engine_model": engine_model,
            "cmapss_unit": int(unit),
            "dataset_split": "train_FD001_holdout",
            "total_life": total_life,
            "max_available_cycle": max_available_cycle,
            "min_observed_true_rul": int(sub["true_rul"].min()),
            "max_observed_true_rul": int(sub["true_rul"].max()),
            "model_family": "lev_week6_oof_residual",
            "feature_count": int(lev_feature_count),
            "start_cycle": int(start_cycle),
        })

        aircrafts_rows.append({
            "aircraft_id": aircraft_id,
            "engine_id": engine_id,
            "model_name": model_name,
            "engine_model": engine_model,
            "current_cycle": int(start_cycle),
            "true_rul": int(start_row["true_rul"]),
            "predicted_rul": float(start_row["pred_oof"]),
            "status": "active",
            "is_active": True,
        })

        for _, r in sub.iterrows():
            cyc = int(r["cycle"])
            for variant, col in (("baseline", "pred_oof"),
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
