#!/usr/bin/env python3
"""Build macOS Dock-ready icon assets with safe-zone padding."""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "assets"
SOURCE_FILE = ASSETS / "meteor_icon_source.png"
PADDED = ASSETS / "meteor_icon_macos.png"
ICONSET = ASSETS / "meteor.iconset"
ICNS = ASSETS / "meteor.icns"

# Meteor palette (matches meteor_gui.py)
BLACK = (0, 0, 0, 255)  # #000000 — circular safe-zone base
PURPLE = (176, 38, 255)  # #B026FF
VIOLET = (124, 58, 237)  # #7C3AED
MAGENTA = (217, 70, 239)  # #D946EF
CORE = (240, 220, 255)

SAFE_INSET = 0.15  # ~15% margin for macOS squircle mask
MARK_SCALE = 0.82  # meteor fits inside black circle

SIZES = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]

SMALL_ICON_THRESHOLD = 32


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _blend(c1: tuple[int, ...], c2: tuple[int, ...], t: float) -> tuple[int, int, int]:
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t), _lerp(c1[2], c2[2], t))


def _rot(cx: float, cy: float, x: float, y: float, angle: float) -> tuple[float, float]:
    ca, sa = math.cos(angle), math.sin(angle)
    return cx + x * ca - y * sa, cy + x * sa + y * ca


def _draw_meteor(
    draw: ImageDraw.ImageDraw,
    size: int,
    *,
    simplified: bool,
) -> None:
    """Draw meteor on transparent canvas; geometry centered at image midpoint."""
    cx = cy = size / 2
    angle = math.radians(-45)

    span = size * 0.78
    head_r = span * 0.14
    tail_len = span * 0.44

    # Local axis: head at origin, tail trails along -x.
    tail_base = -head_r * 0.4
    tail_tip = tail_base - tail_len
    tail_near = head_r * 0.9
    tail_far = head_r * 0.16

    def pt(x: float, y: float) -> tuple[float, float]:
        return _rot(cx, cy, x, y, angle)

    tail_pts = [
        pt(tail_base, -tail_near),
        pt(tail_base, tail_near),
        pt(tail_tip, tail_far),
        pt(tail_tip, -tail_far),
    ]

    if simplified:
        draw.polygon(tail_pts, fill=(*VIOLET, 255))
        hx, hy = pt(0, 0)
        draw.ellipse((hx - head_r, hy - head_r, hx + head_r, hy + head_r), fill=(*PURPLE, 255))
        core_r = head_r * 0.42
        draw.ellipse((hx - core_r, hy - core_r, hx + core_r, hy + core_r), fill=(*MAGENTA, 255))
        dot_r = max(1.0, head_r * 0.2)
        draw.ellipse((hx - dot_r, hy - dot_r, hx + dot_r, hy + dot_r), fill=(*CORE, 255))
        return

    steps = 28
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        color = _blend(VIOLET, MAGENTA, t0 * 0.5 + 0.2)
        band = []
        for sign in (-1, 1):
            x0 = tail_base - tail_len * t0
            x1 = tail_base - tail_len * t1
            y0 = tail_near * (1 - t0) + tail_far * t0
            y1 = tail_near * (1 - t1) + tail_far * t1
            band.append(pt(x0, sign * y0))
            band.append(pt(x1, sign * y1))
        draw.polygon(band, fill=(*color, 255))

    draw.polygon(tail_pts, fill=(*VIOLET, 255))

    hx, hy = pt(0, 0)
    for r_frac, color in (
        (1.25, PURPLE),
        (1.0, VIOLET),
        (0.74, MAGENTA),
        (0.48, PURPLE),
        (0.26, CORE),
    ):
        r = head_r * r_frac
        draw.ellipse((hx - r, hy - r, hx + r, hy + r), fill=(*color, 255))

    hi_r = head_r * 0.11
    hix, hiy = pt(head_r * 0.2, -head_r * 0.24)
    draw.ellipse((hix - hi_r, hiy - hi_r, hix + hi_r, hiy + hi_r), fill=(255, 255, 255, 220))


def _alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    return bbox


def render_meteor_mark(size: int, *, simplified: bool = False, supersample: int = 4) -> Image.Image:
    """Render meteor; supersample small sizes for clean edges."""
    if supersample > 1:
        big = size * supersample
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        _draw_meteor(ImageDraw.Draw(img, "RGBA"), big, simplified=simplified)
        return img.resize((size, size), Image.Resampling.LANCZOS)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _draw_meteor(ImageDraw.Draw(img, "RGBA"), size, simplified=simplified)
    return img


def _safe_inner_diameter(size: int, inset: float = SAFE_INSET) -> int:
    return max(1, int(size * (1 - inset * 2)))


def _draw_black_safe_circle(canvas: Image.Image, size: int, inset: float = SAFE_INSET) -> None:
    """Opaque black disc inscribed in the macOS safe zone (no baked squircle)."""
    inner = _safe_inner_diameter(size, inset)
    radius = inner / 2
    cx = cy = size / 2
    ImageDraw.Draw(canvas, "RGBA").ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=BLACK,
    )


def center_mark_in_canvas(mark: Image.Image, canvas_size: int, inset: float = SAFE_INSET) -> Image.Image:
    """Black circular safe base + centered meteor on transparent outer canvas."""
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    _draw_black_safe_circle(canvas, canvas_size, inset)

    inner = _safe_inner_diameter(canvas_size, inset)
    mark_size = max(1, int(inner * MARK_SCALE))
    bbox = _alpha_bbox(mark)
    if bbox is None:
        return canvas

    cropped = mark.crop(bbox)
    fitted = cropped.resize((mark_size, mark_size), Image.Resampling.LANCZOS)
    offset = (canvas_size - mark_size) // 2
    canvas.alpha_composite(fitted, (offset, offset))
    return canvas


def composite_on_bg(mark: Image.Image, bg: tuple[int, int, int, int]) -> Image.Image:
    flat = Image.new("RGBA", mark.size, bg)
    flat.alpha_composite(mark)
    return flat


def build_icon_frame(
    size: int,
    *,
    simplified: bool = False,
    supersample: int = 1,
    inset: float = SAFE_INSET,
) -> Image.Image:
    inner = max(1, int(size * (1 - inset * 2)))
    ss = supersample
    if size <= 32:
        ss = max(ss, 4)
    elif size <= 64:
        ss = max(ss, 2)
    mark = render_meteor_mark(inner, simplified=simplified, supersample=ss)
    return center_mark_in_canvas(mark, size, inset)


def write_png_sizes() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    master = build_icon_frame(1024, simplified=False, supersample=1)
    master.save(PADDED)
    master.save(ASSETS / "meteor_icon.png")
    master.save(ASSETS / "meteor_icon_1024.png")
    master.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / "meteor_icon_256.png")

    tk_frame = build_icon_frame(64, simplified=True, supersample=4)
    composite_on_bg(tk_frame, BLACK).save(ASSETS / "meteor_icon_64.png")

    # Write-only export — never read back as pipeline input.
    render_meteor_mark(1024, simplified=False, supersample=1).save(SOURCE_FILE)

    if ICONSET.exists():
        shutil.rmtree(ICONSET)
    ICONSET.mkdir()

    for name, px in SIZES:
        simplified = px <= SMALL_ICON_THRESHOLD
        build_icon_frame(px, simplified=simplified).save(ICONSET / name)

    subprocess.run(["iconutil", "-c", "icns", str(ICONSET), "-o", str(ICNS)], check=True)
    shutil.rmtree(ICONSET)


def main() -> None:
    write_png_sizes()
    print(f"Built {ICNS}")


if __name__ == "__main__":
    main()
