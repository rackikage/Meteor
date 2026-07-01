#!/usr/bin/env python3
"""Build Meteor's HD icon set — OLED black rounded square with a glowing
purple comet head, gradient tail, and star sparkles. Renders once at 2048px
then downsamples to the target sizes (crisp Lanczos).
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "assets"
MASTER = 2048

BG_DARK   = (10, 7, 16)         # OLED-adjacent black
BG_DEEP   = (0, 0, 0)
ACCENT    = (168, 85, 247)      # #a855f7
ACCENT_HI = (192, 132, 252)     # #c084fc
ACCENT_LO = (124, 58, 237)      # #7c3aed
CORE_WHITE = (255, 245, 255)


def rounded_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    r = int(size * radius_ratio)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=r, fill=255)
    return mask


def vertical_gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        img.putpixel((0, y), tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3)))
    return img.resize((size, size), Image.LANCZOS)


def radial_glow(size: int, color: tuple, cx: float, cy: float,
                inner_r: float, outer_r: float, inner_alpha=255, outer_alpha=0) -> Image.Image:
    """Soft radial glow drawn as many concentric alpha discs."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    steps = 64
    for i in range(steps, 0, -1):
        t = i / steps
        r = inner_r + (outer_r - inner_r) * t
        a = int(outer_alpha + (inner_alpha - outer_alpha) * (1 - t) ** 2.2)
        if a <= 0:
            continue
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, a))
    return layer


def draw_comet_tail(size: int, head: tuple, tail_end: tuple, thickness: float) -> Image.Image:
    """A purple comet tail — thick near the head, feathering to nothing at the end.
    Rendered as many overlapping ellipses along the vector, then blurred."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    hx, hy = head
    ex, ey = tail_end
    steps = 240
    for i in range(steps):
        t = i / steps
        x = hx + (ex - hx) * t
        y = hy + (ey - hy) * t
        # Thickness tapers from `thickness` down to ~0
        w = thickness * (1 - t) ** 1.3
        # Two-color blend along tail: hot near head, deep purple at end
        c = (
            int(CORE_WHITE[0] * (1 - t) ** 3 + ACCENT[0] * (1 - (1 - t) ** 3)),
            int(CORE_WHITE[1] * (1 - t) ** 3 + ACCENT[1] * (1 - (1 - t) ** 3)),
            int(CORE_WHITE[2] * (1 - t) ** 3 + ACCENT[2] * (1 - (1 - t) ** 3)),
        )
        a = int(255 * (1 - t) ** 1.4)
        draw.ellipse((x - w, y - w, x + w, y + w), fill=(*c, a))
    return layer.filter(ImageFilter.GaussianBlur(radius=size * 0.006))


def draw_stars(size: int, count: int = 28) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rng = random.Random(1337)
    for _ in range(count):
        x = rng.uniform(size * 0.05, size * 0.95)
        y = rng.uniform(size * 0.05, size * 0.95)
        # Avoid drawing over the comet head/tail band
        # (approx line from (0.72, 0.28) → (0.15, 0.85))
        # Distance to line:
        p1, p2 = (size * 0.72, size * 0.28), (size * 0.15, size * 0.85)
        line_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        d = abs((p2[1] - p1[1]) * x - (p2[0] - p1[0]) * y + p2[0] * p1[1] - p2[1] * p1[0]) / line_len
        if d < size * 0.06:
            continue
        r = rng.uniform(size * 0.0015, size * 0.006)
        a = rng.randint(120, 230)
        # Occasional purple star
        c = ACCENT_HI if rng.random() < 0.25 else (240, 235, 250)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(*c, a))
        # Cross-flare sparkle for the brightest few
        if r > size * 0.004:
            for dx, dy in ((r * 3, 0), (-r * 3, 0), (0, r * 3), (0, -r * 3)):
                draw.ellipse((x + dx - r * 0.4, y + dy - r * 0.4,
                              x + dx + r * 0.4, y + dy + r * 0.4),
                             fill=(*c, a // 3))
    return layer.filter(ImageFilter.GaussianBlur(radius=size * 0.001))


def build_master() -> Image.Image:
    size = MASTER
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 255))

    # ── Background: deep purple-black vertical gradient ────────────
    bg = vertical_gradient(size, BG_DARK, BG_DEEP).convert("RGBA")
    canvas.alpha_composite(bg)

    # Subtle nebula wash — a huge, very soft purple radial in the top-right
    nebula = radial_glow(size, ACCENT_LO,
                         cx=size * 0.78, cy=size * 0.22,
                         inner_r=size * 0.02, outer_r=size * 0.55,
                         inner_alpha=95, outer_alpha=0)
    canvas.alpha_composite(nebula)

    # Stars
    canvas.alpha_composite(draw_stars(size, count=34))

    # ── Comet tail (drawn first so head sits on top) ───────────────
    head = (size * 0.72, size * 0.28)
    tail_end = (size * 0.15, size * 0.85)
    canvas.alpha_composite(draw_comet_tail(size, head, tail_end, thickness=size * 0.045))

    # ── Comet head — layered glow, then hot white core ─────────────
    # Outer purple glow
    canvas.alpha_composite(radial_glow(size, ACCENT,
                                       cx=head[0], cy=head[1],
                                       inner_r=size * 0.05,
                                       outer_r=size * 0.28,
                                       inner_alpha=210, outer_alpha=0))
    # Mid magenta glow
    canvas.alpha_composite(radial_glow(size, ACCENT_HI,
                                       cx=head[0], cy=head[1],
                                       inner_r=size * 0.02,
                                       outer_r=size * 0.12,
                                       inner_alpha=255, outer_alpha=0))
    # Hot white core
    canvas.alpha_composite(radial_glow(size, CORE_WHITE,
                                       cx=head[0], cy=head[1],
                                       inner_r=size * 0.001,
                                       outer_r=size * 0.055,
                                       inner_alpha=255, outer_alpha=0))

    # Cross-flare lens spikes on the head
    flare = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(flare)
    hx, hy = head
    for angle in (0, 90, 45, -45):
        rad = math.radians(angle)
        dx = math.cos(rad) * size * 0.16
        dy = math.sin(rad) * size * 0.16
        for i in range(1, 40):
            t = i / 40
            r = size * 0.004 * (1 - t)
            x = hx + dx * t
            y = hy + dy * t
            a = int(220 * (1 - t) ** 2)
            fdraw.ellipse((x - r, y - r, x + r, y + r),
                          fill=(*CORE_WHITE, a))
            x2 = hx - dx * t
            y2 = hy - dy * t
            fdraw.ellipse((x2 - r, y2 - r, x2 + r, y2 + r),
                          fill=(*CORE_WHITE, a))
    canvas.alpha_composite(flare.filter(ImageFilter.GaussianBlur(radius=size * 0.002)))

    # ── Rounded-square mask + accent border ────────────────────────
    mask = rounded_mask(size, radius_ratio=0.225)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(canvas, (0, 0), mask=mask)

    # Thin inner accent stroke
    border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(border)
    stroke_w = max(2, size // 340)
    r = int(size * 0.225)
    bdraw.rounded_rectangle(
        (stroke_w, stroke_w, size - stroke_w, size - stroke_w),
        radius=r - stroke_w,
        outline=(*ACCENT, 90),
        width=stroke_w,
    )
    out.alpha_composite(border)

    return out


def main() -> None:
    master = build_master()

    # Save the source at full res + resample to standard sizes.
    ASSETS.mkdir(exist_ok=True)
    master.save(ASSETS / "meteor_icon_source.png", format="PNG", optimize=True)

    sizes = {
        "meteor_icon.png": 512,
        "meteor_icon_64.png": 64,
        "meteor_icon_256.png": 256,
        "meteor_icon_1024.png": 1024,
        "meteor_icon_macos.png": 1024,
    }
    for name, s in sizes.items():
        master.resize((s, s), Image.LANCZOS).save(ASSETS / name, format="PNG", optimize=True)

    # Multi-resolution .ico for Windows
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    icos = [master.resize((s, s), Image.LANCZOS) for s in ico_sizes]
    icos[0].save(ASSETS / "meteor.ico", format="ICO",
                 sizes=[(s, s) for s in ico_sizes], append_images=icos[1:])

    print(f"Icons written to {ASSETS}")


if __name__ == "__main__":
    main()
