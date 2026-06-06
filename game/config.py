"""Central configuration: economics, statuses, palette, fleet layout."""
from __future__ import annotations

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
ASSETS_DIR = PROJECT_DIR / "assets"

GAME_TITLE = "PADII RUL Engineer"
GAME_TAGLINE = "Прими инженерные решения на основе прогноза RUL"

# --- economics -------------------------------------------------------------
START_BUDGET = 100_000
FLIGHT_REVENUE = 5_000
MAINTENANCE_COST = 50_000
CRASH_PENALTY = 5_000_000

# --- RUL status thresholds (on PREDICTED rul) ------------------------------
SAFE_MIN = 20          # RUL > 20  -> Safe
WARNING_MIN = 5        # 5 <= RUL <= 20 -> Warning ; RUL < 5 -> Critical

STATUS_SAFE = "Safe"
STATUS_WARNING = "Warning"
STATUS_CRITICAL = "Critical"


def status_for_rul(rul: float) -> str:
    if rul > SAFE_MIN:
        return STATUS_SAFE
    if rul >= WARNING_MIN:
        return STATUS_WARNING
    return STATUS_CRITICAL


# --- model variants --------------------------------------------------------
MODEL_VARIANTS = {
    "baseline": {
        "label": "Baseline Model",
        "desc": "Максимизирует точность. Может опасно переоценивать остаточный ресурс.",
    },
    "safety_aware": {
        "label": "Safety-Aware Model",
        "desc": "Штрафует завышение RUL. Прогнозирует осторожнее — меньше риск аварий.",
    },
}

# --- colour palette (industrial / engineering) -----------------------------
COL = {
    "bg": "#0d1420",
    "panel": "#16202e",
    "panel_light": "#1e2c3e",
    "panel_edge": "#2c3e54",
    "ink": "#e8eef6",
    "ink_dim": "#8aa0b8",
    "accent": "#36c2f6",
    "accent_dark": "#1c6f96",
    "safe": "#3fd07a",
    "warning": "#f5b53d",
    "critical": "#ef4d4d",
    "primary": "#2fa84f",        # Continue Flight
    "primary_edge": "#1f7d3a",
    "danger": "#b8453f",          # Maintenance
    "gold": "#f2c14e",
}

# --- pixel scene -----------------------------------------------------------
# The scene is composited from real PNG art (assets/) on top of location.png.
SCENE_W = 960
SCENE_H = 640
SCENE_SCALE = 1  # render directly at display resolution

# parking spots for the 3 aircraft, (cx, cy) in scene space (centre of plane)
PARKING_SPOTS = [
    (210, 470),
    (480, 470),
    (750, 470),
]

PLANE_WIDTH = 236   # on-map big_plane width in px

# decorative ground vehicles: (asset, cx, cy, target_height)
DECOR = [
    ("car_stairs.png", 360, 360, 110),
    ("food_car.png", 110, 575, 92),
    ("petrol_car.png", 858, 568, 96),
]
