"""Render cat/heart frames and pack shared animations for ESP32 and HTML.

Requires Pillow. Run from any directory: python tools/build_animation_assets.py
The exported PNG pixels and RGB565 runs are checked for an exact match.
"""
from base64 import b64encode
from io import BytesIO
from math import cos, pi, sin, exp
from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
FRAME_COUNT = 32


def foot(phase, anchor_x):
    """A planted foot travels backwards locally at the screen travel speed."""
    phase %= 1
    if phase < 0.65:
        return anchor_x - 20 + 40*phase/0.65, 119.0
    swing = (phase-0.65)/0.35
    ease = swing*swing*(3-2*swing)
    return anchor_x + 20 - 40*ease, 119 - 13*sin(pi*swing)


def cat_frame(phase):
    """Original pixel cat: front-facing green eyes, side-on body, curled tail."""
    image = Image.new("RGB", (48, 33), "black")
    draw = ImageDraw.Draw(image)
    outline, shade, light, white = "#49485f", "#9baeb8", "#d5e5e5", "#f7fffc"
    bob = int(cos(phase*4*pi) > 0.35)

    def polygon(points, color):
        draw.polygon([(x, y+bob) for x, y in points], fill=color)

    def leg(front, offset, far):
        hip_x = 19 if front else 32
        toe_x, toe_y = foot(phase+offset, hip_x*4)
        toe_x, toe_y = round(toe_x/4), round(toe_y/4)
        hip = (hip_x, 22+bob)
        # Elbows face back; rear hocks fold forward during the swing.
        knee = (round((hip_x+toe_x)/2)+(1 if front else -1), 25+bob)
        ankle = (toe_x+1, toe_y-1)
        points = [hip, knee, ankle]
        color = shade if far else white
        draw.line(points, fill=outline, width=3 if far else 4)
        draw.rectangle((toe_x-2, toe_y-1, toe_x+1, toe_y+1), fill=outline)
        draw.line(points, fill=color, width=2)
        draw.line((toe_x-1, toe_y, toe_x+1, toe_y), fill=color, width=1)
        if not far:
            draw.point((toe_x+1, toe_y-1), fill=light)

    # The tail rises from the rump, ending in a little inward hook.
    sway = round(sin(phase*2*pi))
    tail = [(34, 19+bob), (38+sway, 15), (41+sway, 10),
            (41+sway, 6), (40+sway, 4), (37+sway, 4), (35+sway, 6)]
    draw.line(tail, fill=outline, width=4)
    draw.line(tail, fill=light, width=2)
    draw.line([(x, y-1) for x, y in tail], fill=white, width=1)

    leg(False, 0.77, True)
    leg(True, 0.52, True)
    leg(False, 0.25, False)
    leg(True, 0.0, False)

    # A compact stepped silhouette, with a small shoulder and rounded haunch.
    polygon([(17, 16), (20, 15), (27, 15), (29, 16), (33, 16),
             (36, 18), (37, 21), (35, 24), (30, 25), (25, 24),
             (21, 24), (19, 26), (16, 25)], outline)
    polygon([(18, 17), (21, 16), (26, 16), (29, 17), (33, 17),
             (35, 19), (36, 21), (34, 23), (30, 24), (25, 23),
             (21, 23), (18, 25), (17, 24)], light)
    polygon([(18, 17), (21, 16), (26, 16), (29, 17), (33, 17),
             (35, 19), (35, 21), (33, 22), (26, 22), (24, 21),
             (21, 22), (18, 24)], white)

    # Large square head, two pointed ears, no tiny facial lines to lose on LCD.
    polygon([(6, 11), (7, 9), (8, 6), (10, 8), (11, 9),
             (15, 9), (18, 6), (19, 8), (20, 11), (21, 12),
             (21, 18), (19, 20), (16, 21), (9, 20), (6, 18)], outline)
    polygon([(7, 12), (8, 10), (9, 8), (11, 11), (15, 11),
             (18, 8), (19, 11), (20, 12), (20, 17),
             (18, 19), (16, 20), (9, 19), (7, 17)], light)
    polygon([(7, 12), (8, 10), (9, 8), (11, 11), (15, 11),
             (18, 8), (19, 11), (19, 17), (17, 19),
             (10, 19), (7, 17)], white)
    draw.rectangle((10, 13+bob, 11, 15+bob), fill="#81ce58")
    draw.rectangle((15, 13+bob, 16, 15+bob), fill="#81ce58")
    draw.point((10, 13+bob), fill="#b0e88b")
    draw.point((15, 13+bob), fill="#b0e88b")
    return image.resize((192, 132), Image.Resampling.NEAREST)


def pixel_heart(colors=("#b51042", "#ff326c", "#df164f", "#ffb6ce"), size=(16, 15)):
    """Mirror the silhouette before coloring, so every size stays symmetric."""
    outline, fill, shade, highlight = colors
    rows = ["..####....####..", ".######..######."] + ["################"]*6
    rows += [".##############.", "..############..", "...##########...",
             "....########....", ".....######.....", "......####......", ".......##......."]
    mask = Image.new("L", (16, 15))
    mask.putdata([255 if cell == "#" else 0 for row in rows for cell in row])
    mask = mask.resize(size, Image.Resampling.NEAREST)
    width, height = size
    mask.paste(ImageOps.mirror(mask.crop((0, 0, width//2, height))), (width//2, 0))
    pixel = Image.new("RGB", size, "black")
    draw = ImageDraw.Draw(pixel)
    for y in range(height):
        for x in range(width):
            if not mask.getpixel((x, y)):
                continue
            edge = any(not (0 <= nx < width and 0 <= ny < height) or not mask.getpixel((nx, ny))
                       for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)))
            shadow = (x+0.5)*16/width + (y+0.5)*15/height > 18
            draw.point((x, y), fill=outline if edge else (shade if shadow else fill))
    # Place the old stepped glint after resizing the symmetric silhouette.
    draw.line((round(3*width/16), round(2*height/15),
               round(5*width/16), round(2*height/15)), fill=highlight)
    draw.line((round(2*width/16), round(3*height/15),
               round(2*width/16), round(4*height/15)), fill=highlight)
    return pixel


def heart_frame(phase):
    pixel = pixel_heart()
    first = (phase-0.10+0.5) % 1 - 0.5
    second = (phase-0.30+0.5) % 1 - 0.5
    beat = exp(-(first/0.065)**2) + 0.65*exp(-(second/0.075)**2)
    size = (14+round(2*beat), 13+round(2*beat))
    heart = pixel.resize(size, Image.Resampling.NEAREST).resize(
        (size[0]*4, size[1]*4), Image.Resampling.NEAREST)
    image = Image.new("RGB", (72, 72), "black")
    image.paste(heart, ((72-heart.width)//2, (72-heart.height)//2))
    return image


def floating_heart_frame(phase):
    # Integer scaling preserves the exact outline and shading of the BF heart.
    style = int(phase*FRAME_COUNT) % FRAME_COUNT
    colors = [("#b51042", "#ff326c", "#df164f", "#ffb6ce"),
              ("#9b1437", "#ff465e", "#d62045", "#ffc3ce"),
              ("#b93f79", "#ff87ba", "#df5296", "#ffe0ef"),
              ("#82256c", "#e45dbb", "#b53492", "#ffbde9")]
    scale = 1 if style % 8 < 4 else 2
    heart = pixel_heart(colors[style//8]).resize((16*scale, 15*scale), Image.Resampling.NEAREST)
    image = Image.new("RGB", (44, 44), "black")
    image.paste(heart, ((44-heart.width)//2, (44-heart.height)//2))
    return image


def rgb565(pixel):
    r, g, b = pixel
    return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)


def expand565(value):
    return (round(((value >> 11) & 31)*255/31),
            round(((value >> 5) & 63)*255/63), round((value & 31)*255/31))


def pack(name, frames, period=None):
    width, height = frames[0].size
    frame_count = len(frames)
    atlas = Image.new("RGB", (width*8, height*((frame_count+7)//8)))
    for index, frame in enumerate(frames):
        atlas.paste(frame, ((index % 8)*width, (index//8)*height))
    reduced = atlas.quantize(colors=96, dither=Image.Dither.NONE).convert("RGB")
    raw = reduced.tobytes()
    values = [rgb565(raw[i:i+3]) for i in range(0, len(raw), 3)]
    palette = sorted(set(values) | {0})
    lookup = {value: index for index, value in enumerate(palette)}
    data, offsets = [], [0]
    indexed = Image.new("P", atlas.size)
    png_palette = [channel for value in palette for channel in expand565(value)]
    indexed.putpalette(png_palette + [0]*(768-len(png_palette)))
    indexed.putdata([lookup[value] for value in values])
    for index in range(frame_count):
        pixels = []
        for y in range(height):
            start = ((index//8)*height+y)*atlas.width+(index % 8)*width
            row = values[start:start+width]
            x = 0
            while x < width:
                end = x+1
                while end < width and row[end] == row[x] and end-x < 255:
                    end += 1
                data.extend((end-x, lookup[row[x]]))
                pixels.extend([row[x]]*(end-x))
                x = end
        # Decode the exported format, independent of the run writer.
        decoded = []
        for cursor in range(offsets[-1], len(data), 2):
            decoded.extend([palette[data[cursor+1]]]*data[cursor])
        assert decoded == pixels and len(decoded) == width*height
        offsets.append(len(data))
    output = BytesIO()
    # Transparent black matches the ESP32 decoder, which skips zero-color runs.
    indexed.save(output, format="PNG", optimize=True, transparency=lookup[0])
    png = output.getvalue()
    asset_dir = ROOT / "assets"
    asset_dir.mkdir(exist_ok=True)
    (asset_dir / f"{name}.png").write_bytes(png)
    if name == "cat-walk":
        poses = [indexed.crop(((i % 8)*width, (i//8)*height,
                               (i % 8+1)*width, (i//8+1)*height))
                 .resize((width*2, height*2), Image.Resampling.NEAREST)
                 for i in range(FRAME_COUNT)]
        poses[0].save(asset_dir / "cat-preview.gif", save_all=True,
                      append_images=poses[1:], duration=([30]*7+[40])*4,
                      loop=0, optimize=False)
    def array(c_type, label, items, digits):
        lines = [f"static const {c_type} {label}[] PROGMEM = {{"]
        for offset in range(0, len(items), 20):
            lines.append("  " + ",".join(f"0x{value:0{digits}X}" for value in items[offset:offset+20]) + ",")
        return "\n".join(lines) + "\n};\n"
    prefix = name.upper().replace("-", "_")
    header = array("uint16_t", f"{prefix}_PALETTE", palette, 4)
    header += array("uint32_t", f"{prefix}_OFFSETS", offsets, 6)
    header += array("uint8_t", f"{prefix}_DATA", data, 2)
    header += (f"static const AnimationAsset {prefix} = "
               f"{{{width}, {height}, {frame_count}, {prefix}_PALETTE, {prefix}_OFFSETS, {prefix}_DATA}};\n")
    metadata = dict(width=width, height=height, frames=frame_count, columns=8,
                    uri="data:image/png;base64," + b64encode(png).decode())
    if period is not None:
        header += f"static constexpr uint32_t {prefix}_PERIOD_MS = {period};\n"
        metadata["period"] = period
        poses = [indexed.crop(((i % 8)*width, (i//8)*height,
                               (i % 8+1)*width, (i//8+1)*height)).convert("RGB")
                 for i in range(frame_count)]
        # GIF timing has 10 ms precision; distribute rounding without drift.
        durations = [(round((i+1)*period/frame_count/10)-round(i*period/frame_count/10))*10
                     for i in range(frame_count)]
        poses[0].save(asset_dir / f"{name}-preview.gif", save_all=True,
                      append_images=poses[1:], duration=durations, loop=0)
    print(f"{name}: {frame_count} frames, {width}x{height}, {len(palette)} colors, {len(data):,} RLE bytes")
    return header, metadata


def main():
    # Stance must cancel the body's screen travel, so paws do not skate.
    for phase in (0.1, 0.3, 0.5):
        assert abs((foot(phase+0.01, 67)[0]-foot(phase, 67)[0]) - 40*0.01/0.65) < 1e-9
    for renderer in (cat_frame, heart_frame):
        assert renderer(0).tobytes() == renderer(1).tobytes(), "Animation must loop without a pose jump"
    assets, header_parts = {}, []
    for name, renderer in (("cat-walk", cat_frame), ("heart-beat", heart_frame),
                           ("floating-hearts", floating_heart_frame)):
        frames = [renderer(index/FRAME_COUNT) for index in range(FRAME_COUNT)]
        if name == "cat-walk":
            bounds = [frame.getbbox() for frame in frames]
            crop = (min(box[0] for box in bounds), min(box[1] for box in bounds),
                    max(box[2] for box in bounds), max(box[3] for box in bounds))
            frames = [frame.crop(crop) for frame in frames]
        header, metadata = pack(name, frames)
        header_parts.append(header)
        assets[name] = metadata
    video = json.loads((ROOT / "assets/bad-apple-source.json").read_text(encoding="utf-8"))
    with Image.open(ROOT / "assets/bad-apple-source.png") as sheet:
        width, height, columns = video["width"], video["height"], video["columns"]
        frames = [sheet.crop(((i % columns)*width, (i//columns)*height,
                              (i % columns+1)*width, (i//columns+1)*height)).convert("RGB")
                  for i in range(video["frames"])]
    header, metadata = pack("bad-apple", frames, video["period"])
    header_parts.append(header)
    assets["bad-apple"] = metadata
    header = ("// Generated by tools/build_animation_assets.py; do not edit bitmap data.\n"
              "#pragma once\n#include <Arduino.h>\n"
              "struct AnimationAsset {\n"
              "  uint16_t width, height, frameCount;\n"
              "  const uint16_t *palette;\n  const uint32_t *offsets;\n  const uint8_t *data;\n};\n")
    (ROOT / "Hairclip/AnimationAssets.h").write_text(header + "\n".join(header_parts), encoding="utf-8")
    preview = ROOT / "preview.html"
    html = preview.read_text(encoding="utf-8")
    begin, end = "// BEGIN GENERATED ANIMATION ASSETS", "// END GENERATED ANIMATION ASSETS"
    before, separator, tail = html.partition(begin)
    assert separator and end in tail, "Missing asset markers in preview.html"
    tail = tail.partition(end)[2]
    html = before + begin + "\n      const animationAssets = " + json.dumps(assets, separators=(",", ":")) + ";\n      " + end + tail
    preview.write_text(html, encoding="utf-8")
    print("Shared PNG / RGB565 frames generated and decoded successfully.")


if __name__ == "__main__":
    main()
