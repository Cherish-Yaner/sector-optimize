#!/usr/bin/env python3
"""
Author: 你
Date  : 2025‑05‑02
"""

import argparse
from pathlib import Path
from PIL import Image

# 明暗映射表：索引 0 为最“黑”使用的字符
ASCII_CHARS = "@%#*+=-:. "     # 可自行增减或调整顺序

def to_ascii(img: Image.Image, width: int, invert: bool) -> str:
    """把 PIL 图像对象转成 ASCII 字符串。"""
    # 按宽度等比缩放（字符高度约为宽度的 2 倍，故再缩放 0.5）
    w, h = img.size
    new_h = int(h * (width / w) * 0.5)
    img = img.resize((width, new_h))
    # 灰度化
    img = img.convert("L")      # L = 8‑bit 灰度
    pixels = img.getdata()

    if invert:
        chars = ASCII_CHARS[::-1]
    else:
        chars = ASCII_CHARS

    step = 256 // len(chars) + 1     # 每多少亮度映射为一个字符
    mapped = [chars[p // step] for p in pixels]

    # 组装行
    rows = [
        "".join(mapped[i:i + width])
        for i in range(0, len(mapped), width)
    ]
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(
        description="Convert PNG / JPEG / … to ASCII art"
    )
    ap.add_argument("image", type=Path, help="input image path")
    ap.add_argument("-W", "--width", type=int, default=100,
                    help="output character width (default 100)")
    ap.add_argument("--invert", action="store_true",
                    help="invert brightness mapping")
    args = ap.parse_args()

    if not args.image.exists():
        ap.error(f"File not found: {args.image}")

    with Image.open(args.image) as im:
        ascii_art = to_ascii(im, args.width, args.invert)
        print(ascii_art)

if __name__ == "__main__":
    main()
