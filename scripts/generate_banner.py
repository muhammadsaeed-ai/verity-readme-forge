"""Generate ReadmeForge's animated README banner using Pillow."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 960, 400
OUTPUT = Path("assets/readmeforge/readmeforge-banner.gif")


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    base = "/usr/share/fonts/truetype/dejavu/"
    name = "DejaVuSansMono.ttf" if mono else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    try:
        return ImageFont.truetype(base + name, size)
    except OSError:
        return ImageFont.load_default()


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, size: int, color: tuple[int, int, int, int], *, bold: bool = False, mono: bool = False) -> None:
    draw.text(xy, value, font=font(size, bold=bold, mono=mono), fill=color)


def create_frame(index: int) -> Image.Image:
    progress = index / 11
    image = Image.new("RGB", (WIDTH, HEIGHT), (5, 10, 22))
    draw = ImageDraw.Draw(image, "RGBA")
    for x in range(0, WIDTH, 24):
        draw.line((x, 0, x, HEIGHT), fill=(45, 82, 126, 24), width=1)
    for y in range(0, HEIGHT, 24):
        draw.line((0, y, WIDTH, y), fill=(45, 82, 126, 24), width=1)
    draw.ellipse((620, -110, 1060, 330), fill=(28, 85, 200, 24))
    draw.ellipse((-150, 240, 430, 700), fill=(18, 100, 120, 20))

    draw.rounded_rectangle((30, 22, 73, 65), radius=12, fill=(8, 39, 63, 255), outline=(54, 222, 249, 255), width=2)
    label(draw, (42, 27), "R", 25, (120, 239, 255, 255), bold=True)
    # Render the wordmark in one text run to avoid overlap and awkward kerning.
    label(draw, (88, 24), "ReadmeForge", 29, (238, 246, 255, 255), bold=True)
    label(draw, (90, 54), "VERITYAGENT · DEVELOPER TOOLING", 9, (126, 169, 207, 255), bold=True)
    draw.rounded_rectangle((755, 26, 928, 55), radius=14, fill=(10, 38, 53, 255), outline=(45, 141, 162, 255), width=1)
    draw.ellipse((768, 36, 776, 44), fill=(81, 229, 184, 255))
    label(draw, (784, 34), "LOCAL-FIRST", 10, (196, 239, 242, 255), bold=True)

    label(draw, (32, 96), "Every repo has a story.", 27, (242, 247, 255, 255), bold=True)
    label(draw, (32, 130), "Forge the README.", 27, (62, 221, 246, 255), bold=True)
    label(draw, (34, 171), "Inspect structure / Detect scripts / Explain the layout", 11, (157, 182, 210, 255))

    draw.rounded_rectangle((28, 207, 447, 353), radius=13, fill=(6, 16, 31, 255), outline=(39, 78, 111, 255), width=1)
    draw.rounded_rectangle((28, 207, 447, 236), radius=13, fill=(15, 34, 55, 255), outline=(39, 78, 111, 255), width=1)
    draw.rectangle((28, 222, 447, 236), fill=(15, 34, 55, 255))
    for x, color in ((44, (255, 113, 135, 255)), (58, (255, 207, 105, 255)), (72, (75, 225, 178, 255))):
        draw.ellipse((x, 218, x + 6, 224), fill=color)
    label(draw, (91, 215), "readmeforge / generate", 10, (193, 218, 239, 255), bold=True, mono=True)
    entries = [
        ("> readmeforge inspect .", (87, 220, 255, 255)),
        ("OK repository inventory", (78, 229, 186, 255)),
        ("OK manifests and scripts", (78, 229, 186, 255)),
        ("OK architecture outline", (78, 229, 186, 255)),
        ("-> rendering README draft", (185, 169, 255, 255)),
    ]
    visible = min(len(entries), 1 + int(progress * len(entries)))
    for row, (value, color) in enumerate(entries[:visible]):
        label(draw, (45, 250 + row * 18), value, 10, color, mono=True)
    draw.rounded_rectangle((45, 338, 430, 343), radius=3, fill=(25, 48, 71, 255))
    draw.rounded_rectangle((45, 338, 45 + max(5, int(385 * progress)), 343), radius=3, fill=(53, 218, 248, 255))

    draw.rounded_rectangle((466, 83, 931, 353), radius=15, fill=(7, 17, 32, 255), outline=(42, 80, 117, 255), width=1)
    draw.rounded_rectangle((466, 83, 931, 115), radius=15, fill=(15, 33, 54, 255), outline=(42, 80, 117, 255), width=1)
    draw.rectangle((466, 101, 931, 115), fill=(15, 33, 54, 255))
    label(draw, (483, 94), "GENERATED DOCUMENTATION PREVIEW", 10, (205, 226, 243, 255), bold=True)
    label(draw, (483, 132), "Project overview", 17, (242, 247, 255, 255), bold=True)
    label(draw, (483, 157), "Manifest-backed summary and install guide", 10, (145, 177, 207, 255))
    nodes = {
        "manifest": (550, 213, (52, 218, 248)),
        "source": (690, 193, (87, 151, 255)),
        "tests": (685, 272, (169, 139, 255)),
        "README": (842, 232, (78, 226, 184)),
    }
    edges = [("manifest", "source"), ("manifest", "tests"), ("source", "README"), ("tests", "README")]
    for edge_index, (source, target) in enumerate(edges):
        x1, y1, _ = nodes[source]
        x2, y2, _ = nodes[target]
        draw.line((x1, y1, x2, y2), fill=(56, 144, 193, 190), width=2)
        ratio = (progress * 1.2 + edge_index * 0.19) % 1
        px, py = x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio
        draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(108, 244, 255, 255))
    for node, (cx, cy, color) in nodes.items():
        pulse = 0.5 + 0.5 * math.sin(index * 0.55 + cx / 20)
        glow = int(35 + 35 * pulse)
        draw.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=(*color, glow))
        draw.rounded_rectangle((cx - 44, cy - 13, cx + 44, cy + 13), radius=7, fill=(10, 31, 51, 255), outline=(*color, 245), width=2 if pulse > 0.75 else 1)
        label(draw, (cx - 31, cy - 6), node, 8, (233, 245, 255, 255), bold=True, mono=True)
    status = "DRAFT READY" if index >= 8 else "MAPPING PROJECT EVIDENCE"
    status_color = (83, 231, 185, 255) if index >= 8 else (97, 218, 246, 255)
    draw.rounded_rectangle((484, 305, 912, 334), radius=12, fill=(10, 34, 48, 255), outline=(44, 109, 132, 255), width=1)
    draw.ellipse((498, 315, 506, 323), fill=status_color)
    label(draw, (516, 312), status, 9, status_color, bold=True)

    label(draw, (31, 378), "LOCAL INSPECTION · NO PROJECT EXECUTION · REVIEW BEFORE PUBLISHING", 9, (104, 143, 178, 255), bold=True)
    label(draw, (926, 378), "MARKDOWN + MERMAID", 9, (87, 206, 232, 255), bold=True)
    return image.resize((800, 333), Image.Resampling.LANCZOS)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [create_frame(index) for index in range(12)]
    palette = frames[0].quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    optimized = [palette] + [item.quantize(palette=palette, dither=Image.Dither.NONE) for item in frames[1:]]
    optimized[0].save(
        OUTPUT,
        save_all=True,
        append_images=optimized[1:],
        duration=[140] * len(optimized),
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size:,} bytes; {len(frames)} frames).")


if __name__ == "__main__":
    main()
