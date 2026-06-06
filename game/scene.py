"""Top-down airport scene composited from real pixel-art PNG assets.

Background: assets/location.png
Aircraft on map: assets/big_plane.png  (one per parking spot)
Engineer: assets/player.png  (next to the selected aircraft)
Decor: assets/car_stairs.png, food_car.png, petrol_car.png

Returns the composed image plus per-aircraft hit-boxes (display-pixel space)
so map clicks can select an aircraft.
"""
from __future__ import annotations

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
    return _sprite("location.png", target_w=W).resize((W, H), Image.LANCZOS)


def _paste_center(canvas: Image.Image, sprite: Image.Image, cx: int, cy: int):
    x = int(cx - sprite.width / 2)
    y = int(cy - sprite.height / 2)
    canvas.alpha_composite(sprite, (x, y))
    return x, y, x + sprite.width, y + sprite.height


def render_airport(fleet, selected_id, status_map, ep_status_map):
    base = _background().copy().convert("RGBA")

    # decorative ground vehicles (behind planes)
    for name, cx, cy, th in config.DECOR:
        _paste_center(base, _sprite(name, target_h=th), cx, cy)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    plane = _sprite("big_plane.png", target_w=config.PLANE_WIDTH)
    pw, ph = plane.width, plane.height
    acc = _hx(config.COL["accent"])

    hitboxes = []
    sel_xy = None
    for i, aircraft_id in enumerate(fleet):
        if i >= len(config.PARKING_SPOTS):
            break
        cx, cy = config.PARKING_SPOTS[i]
        selected = aircraft_id == selected_id
        ep = ep_status_map.get(aircraft_id, "active")
        status = status_map.get(aircraft_id, config.STATUS_SAFE)

        # selection ring (drawn under the plane)
        if selected:
            box = [cx - pw // 2 - 8, cy - ph // 2 - 8,
                   cx + pw // 2 + 8, cy + ph // 2 + 8]
            d.rounded_rectangle(box, radius=14, outline=acc + (255,), width=4)
            d.rounded_rectangle([box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3],
                                radius=16, outline=acc + (90,), width=2)

        x0, y0, x1, y1 = _paste_center(base, plane, cx, cy)

        # dim + marker for finished episodes
        if ep == "crashed":
            shade = Image.new("RGBA", (pw, ph), (10, 14, 20, 120))
            base.alpha_composite(shade, (x0, y0))
            r = _hx(config.COL["critical"]) + (255,)
            d.line([(cx - 34, cy - 24), (cx + 34, cy + 24)], fill=r, width=7)
            d.line([(cx - 34, cy + 24), (cx + 34, cy - 24)], fill=r, width=7)
        elif ep == "maintained":
            shade = Image.new("RGBA", (pw, ph), (10, 14, 20, 70))
            base.alpha_composite(shade, (x0, y0))

        # status light above the tail
        st_rgb = STATUS_RGB[status] + (255,)
        sx, sy = cx, y0 - 14
        d.ellipse([sx - 9, sy - 9, sx + 9, sy + 9], fill=st_rgb,
                  outline=(10, 16, 24, 255), width=2)

        # aircraft label plate
        label = aircraft_id.replace("PADII-", "#")
        d.rounded_rectangle([cx - 26, y1 - 6, cx + 26, y1 + 12],
                            radius=4, fill=(13, 20, 32, 220),
                            outline=acc + (120,))
        d.text((cx - 20, y1 - 4), label, fill=(232, 238, 246, 255))

        hitboxes.append((aircraft_id, x0, y0, x1, y1))
        if selected:
            sel_xy = (x1, y1)

    base.alpha_composite(overlay)

    # engineer next to the selected plane
    if sel_xy is not None:
        eng = _sprite("player.png", target_h=120)
        ex = sel_xy[0] - eng.width // 2
        ey = sel_xy[1] - eng.height + 6
        base.alpha_composite(eng, (max(0, ex), max(0, ey)))

    return base.convert("RGB"), hitboxes


def hit_test(hitboxes, x: float, y: float):
    for aircraft_id, x0, y0, x1, y1 in hitboxes:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return aircraft_id
    return None
