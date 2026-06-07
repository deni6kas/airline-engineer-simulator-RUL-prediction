"""Top-down airport scene composited from real pixel-art PNG assets.

Background: assets/terminal.png
Aircraft on map: assets/big_plane.png / plane_being_fixed.png / crashed_plane.png
Engineer: assets/player.png  (next to the selected aircraft)
Decor: assets/car_stairs.png, food_car.png, petrol_car.png

Returns the composed image plus per-aircraft hit-boxes (display-pixel space)
so map clicks can select an aircraft.
"""
from __future__ import annotations

import json
from functools import lru_cache

from PIL import Image, ImageDraw

from . import config

W, H = config.SCENE_W, config.SCENE_H
ASSETS = config.ASSETS_DIR


def _hx(color: str):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


STATUS_RGB = {
    config.STATUS_SAFE: _hx(config.COL["safe"]),
    config.STATUS_WARNING: _hx(config.COL["warning"]),
    config.STATUS_CRITICAL: _hx(config.COL["critical"]),
}

DEFAULT_LAYOUT = {
    "planes": [
        {"x": 180, "y": 500, "width": 350},
        {"x": 720, "y": 510, "width": 350},
        {"x": 780, "y": 330, "width": 270},
    ],
    "vehicles": [
        {"asset": "car_stairs.png", "x": 430, "y": 490, "height": 90},
        {"asset": "food_car.png", "x": 110, "y": 360, "height": 80},
        {"asset": "petrol_car.png", "x": 850, "y": 460, "height": 70},
    ],
    "engineer": {
        "offset_x": 20,
        "offset_y": 10,
        "height": 70,
    },
}


def load_layout() -> dict:
    """Load editable scene placement from assets/scene_layout.json."""
    path = config.SCENE_LAYOUT_PATH
    if not path.exists():
        save_layout(DEFAULT_LAYOUT)
        return json.loads(json.dumps(DEFAULT_LAYOUT))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(json.dumps(DEFAULT_LAYOUT))

    # Keep the schema forgiving so partial manual edits do not break the app.
    layout = json.loads(json.dumps(DEFAULT_LAYOUT))
    layout.update({k: v for k, v in data.items() if k in layout})
    return layout


def save_layout(layout: dict) -> None:
    config.SCENE_LAYOUT_PATH.write_text(
        json.dumps(layout, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def reset_layout() -> dict:
    save_layout(DEFAULT_LAYOUT)
    return json.loads(json.dumps(DEFAULT_LAYOUT))


@lru_cache(maxsize=32)
def _sprite(name: str, target_w: int | None = None,
            target_h: int | None = None) -> Image.Image:
    im = Image.open(ASSETS / name).convert("RGBA")
    bbox = im.getbbox()          # trim transparent padding
    if bbox:
        im = im.crop(bbox)
    if target_w:
        h = max(1, round(im.height * target_w / im.width))
        im = im.resize((target_w, h), Image.LANCZOS)
    elif target_h:
        w = max(1, round(im.width * target_h / im.height))
        im = im.resize((w, target_h), Image.LANCZOS)
    return im


@lru_cache(maxsize=1)
def _background() -> Image.Image:
    return _sprite("terminal.png", target_w=W).resize((W, H), Image.LANCZOS)


def _paste_center(canvas: Image.Image, sprite: Image.Image, cx: int, cy: int):
    x = int(cx - sprite.width / 2)
    y = int(cy - sprite.height / 2)
    canvas.alpha_composite(sprite, (x, y))
    return x, y, x + sprite.width, y + sprite.height


def _plane_sprite_for_status(aircraft_id: str, ep_status: str) -> str:
    sprites = config.AIRCRAFT_SPRITES.get(aircraft_id, config.DEFAULT_PLANE_SPRITES)
    if ep_status == "crashed":
        return sprites["crashed"]
    if ep_status == "maintained":
        return sprites["maintained"]
    return sprites["active"]


def render_airport(fleet, selected_id, status_map, ep_status_map):
    layout = load_layout()
    base = _background().copy().convert("RGBA")

    # decorative ground vehicles (behind planes)
    for vehicle in layout.get("vehicles", []):
        name = vehicle.get("asset", "")
        cx = int(vehicle.get("x", 0))
        cy = int(vehicle.get("y", 0))
        th = int(vehicle.get("height", 90))
        if name:
            _paste_center(base, _sprite(name, target_h=th), cx, cy)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    acc = _hx(config.COL["accent"])

    hitboxes = []
    sel_xy = None
    for i, aircraft_id in enumerate(fleet):
        plane_slots = layout.get("planes", [])
        if i >= len(plane_slots):
            break
        slot = plane_slots[i]
        cx = int(slot.get("x", 0))
        cy = int(slot.get("y", 0))
        selected = aircraft_id == selected_id
        ep = ep_status_map.get(aircraft_id, "active")
        status = status_map.get(aircraft_id, config.STATUS_SAFE)
        plane = _sprite(
            _plane_sprite_for_status(aircraft_id, ep),
            target_w=int(slot.get("width", config.PLANE_WIDTH)),
        )
        pw, ph = plane.width, plane.height

        # selection ring (drawn under the plane)
        if selected:
            box = [cx - pw // 2 - 8, cy - ph // 2 - 8,
                   cx + pw // 2 + 8, cy + ph // 2 + 8]
            d.rounded_rectangle(box, radius=14, outline=acc + (255,), width=4)
            d.rounded_rectangle([box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3],
                                radius=16, outline=acc + (90,), width=2)

        x0, y0, x1, y1 = _paste_center(base, plane, cx, cy)

        # status light above the tail
        st_rgb = STATUS_RGB[status] + (255,)
        sx, sy = cx, y0 - 14
        d.ellipse([sx - 9, sy - 9, sx + 9, sy + 9], fill=st_rgb,
                  outline=(10, 16, 24, 255), width=2)

        # aircraft label plate
        label = config.aircraft_display_name(aircraft_id)
        if label == aircraft_id:
            label = aircraft_id.replace("PADII-", "#")
        lw = max(52, len(label) * 7 + 12)
        d.rounded_rectangle([cx - lw // 2, y1 - 6, cx + lw // 2, y1 + 12],
                            radius=4, fill=(13, 20, 32, 220),
                            outline=acc + (120,))
        d.text((cx - lw // 2 + 6, y1 - 4), label, fill=(232, 238, 246, 255))

        hitboxes.append((aircraft_id, x0, y0, x1, y1))
        if selected:
            sel_xy = (x1, y1)

    base.alpha_composite(overlay)

    # engineer next to the selected plane
    if sel_xy is not None:
        eng_cfg = layout.get("engineer", DEFAULT_LAYOUT["engineer"])
        eng = _sprite("player.png", target_h=int(eng_cfg.get("height", 118)))
        ex = sel_xy[0] + int(eng_cfg.get("offset_x", 38)) - eng.width // 2
        ey = sel_xy[1] + int(eng_cfg.get("offset_y", 52)) - eng.height
        base.alpha_composite(eng, (max(0, ex), max(0, ey)))

    return base.convert("RGB"), hitboxes


def hit_test(hitboxes, x: float, y: float):
    for aircraft_id, x0, y0, x1, y1 in hitboxes:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return aircraft_id
    return None
