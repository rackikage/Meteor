"""Generate the L·Drago icon: own-twist abstract evil-meteor dragon.

The dragon is our own take, not a Beyblade asset. Sharp angular side profile,
ember + violet + cyan palette, meteor orbit ring, with a small L·DRAGO
wordmark. Light + dark variants.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 512
EMP = (255, 80, 38, 255)
VIO = (138, 92, 255, 255)
CYN = (63, 217, 232, 255)


def hsv(h, s, v, a=255):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255), a)


def draw(size, dark=True):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    panel = (16, 20, 30, 255) if dark else (228, 232, 240, 255)
    inner = (8, 10, 16, 255) if dark else (244, 246, 250, 255)
    border = (45, 52, 72, 255) if dark else (200, 208, 220, 255)
    r = size // 7
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=panel)
    d.rounded_rectangle([10, 10, size - 11, size - 11], radius=r - 4,
                        fill=inner, outline=border, width=2)
    cx, cy = size / 2, size * 0.48
    arc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arc)
    for ang_deg in range(0, 360, 1):
        ang = math.radians(ang_deg)
        rr = size * 0.42
        x = cx + rr * math.cos(ang)
        y = cy + rr * math.sin(ang)
        h = ang_deg / 360
        col = hsv(h, 0.85, 1.0, 150)
        ad.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=col)
    arc = arc.filter(ImageFilter.GaussianBlur(2.5))
    img = Image.alpha_composite(img, arc)
    d = ImageDraw.Draw(img)
    head = (28, 34, 52, 255) if dark else (58, 70, 96, 255)
    profile = [
        (cx - 100, cy + 100),
        (cx - 130, cy + 50), (cx - 140, cy + 10),
        (cx - 130, cy - 30), (cx - 110, cy - 50),
        (cx - 110, cy - 70), (cx - 130, cy - 100), (cx - 90, cy - 110),
        (cx - 80, cy - 130), (cx - 30, cy - 170), (cx + 10, cy - 145),
        (cx + 20, cy - 150), (cx + 70, cy - 175), (cx + 100, cy - 140),
        (cx + 120, cy - 120), (cx + 140, cy - 90),
        (cx + 155, cy - 60),
        (cx + 180, cy - 30), (cx + 200, cy + 0),
        (cx + 195, cy + 20), (cx + 170, cy + 35),
        (cx + 130, cy + 45),
        (cx + 90, cy + 60), (cx + 50, cy + 70),
        (cx + 20, cy + 80), (cx + 40, cy + 115), (cx + 10, cy + 100),
        (cx - 30, cy + 110), (cx - 80, cy + 110), (cx - 100, cy + 100),
    ]
    d.polygon(profile, fill=head, outline=EMP)
    d.line([(cx - 30, cy - 170), (cx + 70, cy - 175), (cx + 120, cy - 120)],
           fill=(50, 60, 86, 255) if dark else (95, 110, 140, 255), width=2)
    eye = [
        (cx + 95, cy - 55), (cx + 145, cy - 50),
        (cx + 148, cy - 20), (cx + 92, cy - 18),
    ]
    d.polygon(eye, fill=(0, 0, 0, 255), outline=EMP)
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(40, 6, -2):
        a = int(255 * (r - 6) / 40)
        gd.ellipse([cx + 118 - r, cy - 38 - r // 3, cx + 118 + r, cy - 38 + r // 3],
                   fill=(255, 90, 50, max(0, a // 4)))
    glow = glow.filter(ImageFilter.GaussianBlur(5))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)
    d.ellipse([cx + 110, cy - 42, cx + 132, cy - 25], fill=EMP)
    d.ellipse([cx + 117, cy - 37, cx + 125, cy - 30], fill=(0, 0, 0))
    d.polygon([(cx + 178, cy + 5), (cx + 195, cy + 12),
               (cx + 178, cy + 18)], fill=EMP)
    d.polygon([(cx + 90, cy + 60), (cx + 170, cy + 35),
               (cx + 130, cy + 50)], fill=(0, 0, 0, 255))
    for x1, y1, x2, y2, x3, y3 in [
        (cx + 100, cy + 58, cx + 108, cy + 72, cx + 116, cy + 60),
        (cx + 130, cy + 50, cx + 138, cy + 65, cx + 146, cy + 52),
        (cx + 155, cy + 42, cx + 162, cy + 55, cx + 170, cy + 45),
    ]:
        d.polygon([(x1, y1), (x2, y2), (x3, y3)], fill=CYN)
    d.line([(cx + 0, cy - 130), (cx + 90, cy - 90)], fill=EMP, width=2)
    try:
        font_l = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font_d = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    except Exception:
        font_l = font_d = None
    d.text((30, size - 76), "L", fill=EMP, font=font_l)
    d.text((74, size - 68), "·DRAGO", fill=VIO, font=font_d)
    for i in range(6):
        ang = i * math.pi / 3
        x = size - 56 + 16 * math.cos(ang)
        y = size - 56 + 16 * math.sin(ang)
        d.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=CYN)
    d.ellipse([size - 60, size - 60, size - 52, size - 52], fill=EMP)
    img = img.filter(ImageFilter.SMOOTH)
    return img


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "app", "ui", "ldrago", "assets")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    for theme in ("dark", "light"):
        img = draw(SIZE, dark=(theme == "dark"))
        path = os.path.join(out_dir, f"meteor-ldrago-{theme}.png")
        img.save(path)
        print(f"wrote {path}")
        for sz in (16, 32, 48, 64, 128, 256):
            img.resize((sz, sz), Image.LANCZOS).save(
                os.path.join(out_dir, f"meteor-ldrago-{theme}-{sz}.png")
            )
    print("done.")


if __name__ == "__main__":
    main()
