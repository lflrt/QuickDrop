"""生成 PWA 图标：蓝色圆角方块 + 白色下载箭头，无字体依赖。

运行：quickdrop/.venv/Scripts/python.exe quickdrop/gen_icons.py
产出：quickdrop/static/icon-192.png、icon-512.png
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "static")


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=(74, 144, 217, 255))
    cx = size // 2
    bar_w = int(size * 0.14)
    d.rectangle(
        [cx - bar_w // 2, int(size * 0.22), cx + bar_w // 2, int(size * 0.54)],
        fill=(255, 255, 255, 255),
    )
    d.polygon(
        [
            (cx - int(size * 0.24), int(size * 0.48)),
            (cx + int(size * 0.24), int(size * 0.48)),
            (cx, int(size * 0.70)),
        ],
        fill=(255, 255, 255, 255),
    )
    return img


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    big = make_icon(512)
    big.save(os.path.join(OUT, "icon-512.png"))
    big.resize((192, 192), Image.LANCZOS).save(os.path.join(OUT, "icon-192.png"))
    print("icons written:", os.path.join(OUT, "icon-192.png"), os.path.join(OUT, "icon-512.png"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
