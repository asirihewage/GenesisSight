"""Generate the app icon (electron/build/icon.ico).

Pure Pillow — draws a rounded dark tile with a teal CCTV camera glyph.
Usage:
    python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "electron" / "build"


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size * 0.05
    # dark navy rounded tile
    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad], radius=size * 0.22, fill=(10, 15, 30, 255)
    )
    u = size / 100.0  # unit
    # camera body
    d.rounded_rectangle(
        [16 * u, 34 * u, 84 * u, 66 * u], radius=6 * u, fill=(34, 211, 238, 255)
    )
    # lens ring + glass
    cx, cy, r = 50 * u, 50 * u, 17 * u
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(13, 27, 48, 255), outline=(255, 255, 255, 220), width=max(2, int(2.2 * u)))
    d.ellipse([cx - 12 * u, cy - 12 * u, cx + 12 * u, cy + 12 * u], fill=(56, 189, 248, 255))
    d.ellipse([cx - 5 * u, cy - 5 * u, cx + 5 * u, cy + 5 * u], fill=(255, 255, 255, 210))
    # antenna / mount
    d.line([62 * u, 34 * u, 66 * u, 22 * u], fill=(34, 211, 238, 255), width=max(2, int(3 * u)))
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rounded_icon(512).save(OUT_DIR / "icon.png")
    frames = [rounded_icon(s) for s in (16, 24, 32, 48, 64, 128, 256)]
    frames[0].save(
        OUT_DIR / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)],
        append_images=frames[1:],
    )
    print(f"icons written to {OUT_DIR}")


def rounded_icon(size: int) -> Image.Image:
    return draw(size)


if __name__ == "__main__":
    main()